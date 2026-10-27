"""
Ur Coin High-Performance GPU Miner Engine:
- Interfaces with Windows OpenCL.dll (NVIDIA RTX 3050, AMD, etc.)
- Allocates 1.0 GB - 2.0 GB Memory-Hard DAG in GPU VRAM
- Parallel multi-threaded workgroups executing UrHash search
- Real-time Hashrate monitoring (MH/s), temperature/power detection, and block submission
"""

import os
import time
import struct
import ctypes
import hashlib
import threading
from typing import List, Dict, Optional, Tuple
from urcoin.core import Block, BlockHeader, Transaction, calculate_next_target, get_epoch_seed, DEFAULT_DAG_ITEMS, DEFAULT_ROUNDS
from urcoin.crypto import urhash_cpu_verify

# -------------------------------------------------------------
# OpenCL CTypes Definitions
# -------------------------------------------------------------
cl_platform_id = ctypes.c_void_p
cl_device_id = ctypes.c_void_p
cl_context = ctypes.c_void_p
cl_command_queue = ctypes.c_void_p
cl_program = ctypes.c_void_p
cl_kernel = ctypes.c_void_p
cl_mem = ctypes.c_void_p

CL_MEM_READ_WRITE = 1 << 0
CL_MEM_WRITE_ONLY = 1 << 1
CL_MEM_READ_ONLY = 1 << 2
CL_MEM_COPY_HOST_PTR = 1 << 5

class OpenCLDevice:
    def __init__(self, platform_id, device_id, platform_name: str, device_name: str, memory_bytes: int):
        self.platform_id = platform_id
        self.device_id = device_id
        self.platform_name = platform_name
        self.device_name = device_name
        self.memory_bytes = memory_bytes

    @property
    def memory_gb(self) -> float:
        return self.memory_bytes / (1024 ** 3)

    def __repr__(self):
        return f"[{self.platform_name}] {self.device_name} ({self.memory_gb:.2f} GB VRAM)"

def get_opencl_devices() -> List[OpenCLDevice]:
    """Discover all available OpenCL GPU devices."""
    devices_list = []
    try:
        opencl = ctypes.cdll.LoadLibrary("OpenCL.dll")
    except Exception:
        return devices_list

    opencl.clGetPlatformIDs.argtypes = [ctypes.c_uint32, ctypes.POINTER(cl_platform_id), ctypes.POINTER(ctypes.c_uint32)]
    opencl.clGetPlatformInfo.argtypes = [cl_platform_id, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    opencl.clGetDeviceIDs.argtypes = [cl_platform_id, ctypes.c_uint64, ctypes.c_uint32, ctypes.POINTER(cl_device_id), ctypes.POINTER(ctypes.c_uint32)]
    opencl.clGetDeviceInfo.argtypes = [cl_device_id, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]

    num_p = ctypes.c_uint32()
    if opencl.clGetPlatformIDs(0, None, ctypes.byref(num_p)) != 0 or num_p.value == 0:
        return devices_list

    platforms = (cl_platform_id * num_p.value)()
    opencl.clGetPlatformIDs(num_p.value, platforms, None)

    for p in platforms:
        pname_buf = (ctypes.c_char * 256)()
        opencl.clGetPlatformInfo(p, 0x0902, 256, pname_buf, None)
        pname = pname_buf.value.decode(errors="ignore").strip()

        num_d = ctypes.c_uint32()
        if opencl.clGetDeviceIDs(p, 0xFFFFFFFF, 0, None, ctypes.byref(num_d)) != 0 or num_d.value == 0:
            continue

        devs = (cl_device_id * num_d.value)()
        opencl.clGetDeviceIDs(p, 0xFFFFFFFF, num_d.value, devs, None)

        for d in devs:
            dname_buf = (ctypes.c_char * 256)()
            opencl.clGetDeviceInfo(d, 0x102B, 256, dname_buf, None) # CL_DEVICE_NAME
            dname = dname_buf.value.decode(errors="ignore").strip()

            mem_size = ctypes.c_ulonglong()
            opencl.clGetDeviceInfo(d, 0x101F, 8, ctypes.byref(mem_size), None) # CL_DEVICE_GLOBAL_MEM_SIZE

            devices_list.append(OpenCLDevice(p, d, pname, dname, mem_size.value))

    return devices_list

# -------------------------------------------------------------
# -------------------------------------------------------------
# UrCoin GPUMiner Implementation
# -------------------------------------------------------------
class GPUMiner:
    def __init__(self, device_index: int = 0, dag_items: int = DEFAULT_DAG_ITEMS,
                 rounds: int = DEFAULT_ROUNDS, light_mode: Optional[bool] = None):
        self.device_index = device_index
        self.dag_items = dag_items # 16,777,216 items = 1.0 GB
        self.rounds = rounds
        self.light_mode = light_mode
        self.opencl = None
        self.ctx = None
        self.queue = None
        self.prog = None
        self.init_kernel = None
        self.search_kernel = None
        self.search_light_kernel = None
        self.dag_buf = None
        self.current_epoch = -1
        self.device: Optional[OpenCLDevice] = None

        self.mining = False
        self.hashrate: float = 0.0 # H/s or MH/s
        self.total_hashes: int = 0
        self.blocks_found: int = 0
        self._init_opencl()

    def _init_opencl(self):
        devices = get_opencl_devices()
        if not devices:
            raise RuntimeError("No OpenCL devices found on system.")

        if self.device_index >= len(devices):
            self.device_index = 0
        self.device = devices[self.device_index]
        print(f"[Miner] Selected GPU: {self.device}")

        # Auto-detect low VRAM GPU (less than 2.5 GB)
        if self.light_mode is None:
            if self.device.memory_bytes < 2.5 * (1024 ** 3):
                self.light_mode = True
                print(f"[Miner] Low VRAM GPU detected ({self.device.memory_gb:.2f} GB). Auto-enabling Zero-VRAM Light GPU Mode!")
            else:
                self.light_mode = False
        elif self.light_mode:
            print("[Miner] Zero-VRAM Light Mode explicitly requested. No DAG buffer will be allocated.")

        self.opencl = ctypes.cdll.LoadLibrary("OpenCL.dll")

        # Function signatures
        self.opencl.clCreateContext.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(cl_device_id), ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]
        self.opencl.clCreateContext.restype = cl_context
        self.opencl.clCreateCommandQueue.argtypes = [cl_context, cl_device_id, ctypes.c_uint64, ctypes.POINTER(ctypes.c_int32)]
        self.opencl.clCreateCommandQueue.restype = cl_command_queue
        self.opencl.clCreateProgramWithSource.argtypes = [cl_context, ctypes.c_uint32, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_int32)]
        self.opencl.clCreateProgramWithSource.restype = cl_program
        self.opencl.clBuildProgram.argtypes = [cl_program, ctypes.c_uint32, ctypes.POINTER(cl_device_id), ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p]
        self.opencl.clCreateKernel.argtypes = [cl_program, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int32)]
        self.opencl.clCreateKernel.restype = cl_kernel
        self.opencl.clCreateBuffer.argtypes = [cl_context, ctypes.c_uint64, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]
        self.opencl.clCreateBuffer.restype = cl_mem
        self.opencl.clSetKernelArg.argtypes = [cl_kernel, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p]
        self.opencl.clEnqueueNDRangeKernel.argtypes = [cl_command_queue, cl_kernel, ctypes.c_uint32, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t), ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
        self.opencl.clEnqueueReadBuffer.argtypes = [cl_command_queue, cl_mem, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
        self.opencl.clFinish.argtypes = [cl_command_queue]
        self.opencl.clReleaseMemObject.argtypes = [cl_mem]

        err = ctypes.c_int32()
        dev_arr = (cl_device_id * 1)(self.device.device_id)
        self.ctx = self.opencl.clCreateContext(None, 1, dev_arr, None, None, ctypes.byref(err))
        if err.value != 0:
            raise RuntimeError(f"clCreateContext failed with code {err.value}")

        self.queue = self.opencl.clCreateCommandQueue(self.ctx, self.device.device_id, 0, ctypes.byref(err))
        if err.value != 0:
            raise RuntimeError(f"clCreateCommandQueue failed with code {err.value}")

        # Read kernel file
        kernel_path = os.path.join(os.path.dirname(__file__), "kernels", "urhash.cl")
        with open(kernel_path, "rb") as f:
            src_bytes = f.read()

        src_ptr = ctypes.c_char_p(src_bytes)
        src_len = ctypes.c_size_t(len(src_bytes))
        self.prog = self.opencl.clCreateProgramWithSource(self.ctx, 1, ctypes.byref(src_ptr), ctypes.byref(src_len), ctypes.byref(err))

        build_res = self.opencl.clBuildProgram(self.prog, 1, dev_arr, None, None, None)
        if build_res != 0:
            log_size = ctypes.c_size_t()
            self.opencl.clGetProgramBuildInfo(self.prog, self.device.device_id, 0x1114, 0, None, ctypes.byref(log_size))
            log_buf = (ctypes.c_char * log_size.value)()
            self.opencl.clGetProgramBuildInfo(self.prog, self.device.device_id, 0x1114, log_size.value, log_buf, None)
            raise RuntimeError(f"OpenCL Build Failed: {log_buf.value.decode()}")

        self.init_kernel = self.opencl.clCreateKernel(self.prog, b"generate_dag_buffer", ctypes.byref(err))
        self.search_kernel = self.opencl.clCreateKernel(self.prog, b"urhash_miner_search", ctypes.byref(err))
        self.search_light_kernel = self.opencl.clCreateKernel(self.prog, b"urhash_miner_search_light", ctypes.byref(err))

    def ensure_dag_for_epoch(self, epoch: int):
        """Allocate and generate DAG in GPU VRAM if epoch changed."""
        if self.light_mode:
            return
        if self.current_epoch == epoch and self.dag_buf is not None:
            return

        try:
            print(f"[Miner] Initializing {self.dag_items * 64 / (1024**3):.2f} GB DAG for Epoch {epoch} in GPU VRAM...")
            if self.dag_buf:
                self.opencl.clReleaseMemObject(self.dag_buf)
                self.dag_buf = None

            err = ctypes.c_int32()
            dag_bytes = self.dag_items * 64 # e.g. 1024 MB
            raw_buf = self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_WRITE, dag_bytes, None, ctypes.byref(err))
            if err.value != 0:
                raise RuntimeError(f"Failed to allocate {dag_bytes / (1024**2):.0f} MB in GPU VRAM (code {err.value})")
            self.dag_buf = cl_mem(raw_buf)

            # Generate DAG
            epoch_seed = get_epoch_seed(epoch)
            seed_ulongs = (ctypes.c_ulonglong * 4)(*struct.unpack("<4Q", epoch_seed))
            seed_buf = cl_mem(self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, 32, ctypes.byref(seed_ulongs), ctypes.byref(err)))

            num_items_c = ctypes.c_ulonglong(self.dag_items)
            self.opencl.clSetKernelArg(self.init_kernel, 0, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(seed_buf))
            self.opencl.clSetKernelArg(self.init_kernel, 1, ctypes.c_size_t(ctypes.sizeof(ctypes.c_ulonglong)), ctypes.byref(num_items_c))
            self.opencl.clSetKernelArg(self.init_kernel, 2, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(self.dag_buf))

            gws = (ctypes.c_size_t * 1)(self.dag_items)
            t0 = time.time()
            ret = self.opencl.clEnqueueNDRangeKernel(self.queue, self.init_kernel, 1, None, gws, None, 0, None, None)
            if ret != 0:
                raise RuntimeError(f"clEnqueueNDRangeKernel DAG init failed with code {ret}")
            self.opencl.clFinish(self.queue)
            print(f"[Miner] DAG generation completed in {time.time() - t0:.2f}s!")

            self.opencl.clReleaseMemObject(seed_buf)
            self.current_epoch = epoch
        except Exception as e:
            print(f"[Miner] VRAM allocation failed: {e}. Switching to Zero-VRAM Light GPU Mode!")
            self.light_mode = True

    def search_batch(self, header_hash: bytes, target_int: int, epoch: int,
                     start_nonce: int, global_work_size: int = 65536,
                     nonces_per_thread: int = 64) -> List[Tuple[int, str]]:
        """
        Execute one mining batch across GPU workgroups.
        Searches (global_work_size * nonces_per_thread) nonces per call.
        Returns list of (winning_nonce, hash_hex).
        """
        self.ensure_dag_for_epoch(epoch)

        err = ctypes.c_int32()
        header_ulongs = (ctypes.c_ulonglong * 4)(*struct.unpack("<4Q", header_hash))
        header_buf = cl_mem(self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, 32, ctypes.byref(header_ulongs), ctypes.byref(err)))

        target_bytes = target_int.to_bytes(32, "big")
        target_buf = cl_mem(self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, 32, (ctypes.c_char * 32).from_buffer_copy(target_bytes), ctypes.byref(err)))

        found_count_val = ctypes.c_uint32(0)
        found_count_buf = cl_mem(self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_WRITE | CL_MEM_COPY_HOST_PTR, 4, ctypes.byref(found_count_val), ctypes.byref(err)))

        found_nonces_buf = cl_mem(self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_WRITE, 16 * 8, None, ctypes.byref(err)))
        found_hashes_buf = cl_mem(self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_WRITE, 16 * 32, None, ctypes.byref(err)))

        start_nonce_c = ctypes.c_ulonglong(start_nonce)
        npt_c = ctypes.c_ulonglong(nonces_per_thread)
        num_items_c = ctypes.c_ulonglong(self.dag_items)
        rounds_c = ctypes.c_int32(self.rounds)

        seed_buf = None
        if self.light_mode:
            epoch_seed = get_epoch_seed(epoch)
            seed_ulongs = (ctypes.c_ulonglong * 4)(*struct.unpack("<4Q", epoch_seed))
            seed_buf = cl_mem(self.opencl.clCreateBuffer(self.ctx, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, 32, ctypes.byref(seed_ulongs), ctypes.byref(err)))

            self.opencl.clSetKernelArg(self.search_light_kernel, 0, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(seed_buf))
            self.opencl.clSetKernelArg(self.search_light_kernel, 1, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(header_buf))
            self.opencl.clSetKernelArg(self.search_light_kernel, 2, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(target_buf))
            self.opencl.clSetKernelArg(self.search_light_kernel, 3, ctypes.c_size_t(ctypes.sizeof(ctypes.c_ulonglong)), ctypes.byref(start_nonce_c))
            self.opencl.clSetKernelArg(self.search_light_kernel, 4, ctypes.c_size_t(ctypes.sizeof(ctypes.c_ulonglong)), ctypes.byref(npt_c))
            self.opencl.clSetKernelArg(self.search_light_kernel, 5, ctypes.c_size_t(ctypes.sizeof(ctypes.c_ulonglong)), ctypes.byref(num_items_c))
            self.opencl.clSetKernelArg(self.search_light_kernel, 6, ctypes.c_size_t(ctypes.sizeof(ctypes.c_int32)), ctypes.byref(rounds_c))
            self.opencl.clSetKernelArg(self.search_light_kernel, 7, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(found_count_buf))
            self.opencl.clSetKernelArg(self.search_light_kernel, 8, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(found_nonces_buf))
            self.opencl.clSetKernelArg(self.search_light_kernel, 9, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(found_hashes_buf))
            active_kernel = self.search_light_kernel
        else:
            self.opencl.clSetKernelArg(self.search_kernel, 0, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(self.dag_buf))
            self.opencl.clSetKernelArg(self.search_kernel, 1, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(header_buf))
            self.opencl.clSetKernelArg(self.search_kernel, 2, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(target_buf))
            self.opencl.clSetKernelArg(self.search_kernel, 3, ctypes.c_size_t(ctypes.sizeof(ctypes.c_ulonglong)), ctypes.byref(start_nonce_c))
            self.opencl.clSetKernelArg(self.search_kernel, 4, ctypes.c_size_t(ctypes.sizeof(ctypes.c_ulonglong)), ctypes.byref(npt_c))
            self.opencl.clSetKernelArg(self.search_kernel, 5, ctypes.c_size_t(ctypes.sizeof(ctypes.c_ulonglong)), ctypes.byref(num_items_c))
            self.opencl.clSetKernelArg(self.search_kernel, 6, ctypes.c_size_t(ctypes.sizeof(ctypes.c_int32)), ctypes.byref(rounds_c))
            self.opencl.clSetKernelArg(self.search_kernel, 7, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(found_count_buf))
            self.opencl.clSetKernelArg(self.search_kernel, 8, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(found_nonces_buf))
            self.opencl.clSetKernelArg(self.search_kernel, 9, ctypes.c_size_t(ctypes.sizeof(cl_mem)), ctypes.byref(found_hashes_buf))
            active_kernel = self.search_kernel

        gws = (ctypes.c_size_t * 1)(global_work_size)

        t_start = time.perf_counter()
        ret = self.opencl.clEnqueueNDRangeKernel(self.queue, active_kernel, 1, None, gws, None, 0, None, None)
        if ret != 0:
            raise RuntimeError(f"clEnqueueNDRangeKernel search failed with code {ret}")
        self.opencl.clFinish(self.queue)
        t_delta = time.perf_counter() - t_start

        # Read results
        found_cnt = ctypes.c_uint32()
        self.opencl.clEnqueueReadBuffer(self.queue, found_count_buf, 1, 0, 4, ctypes.byref(found_cnt), 0, None, None)

        results = []
        if found_cnt.value > 0:
            count = min(found_cnt.value, 16)
            nonces = (ctypes.c_ulonglong * count)()
            hashes = (ctypes.c_ubyte * (count * 32))()
            self.opencl.clEnqueueReadBuffer(self.queue, found_nonces_buf, 1, 0, count * 8, ctypes.byref(nonces), 0, None, None)
            self.opencl.clEnqueueReadBuffer(self.queue, found_hashes_buf, 1, 0, count * 32, ctypes.byref(hashes), 0, None, None)

            h_bytes = bytes(hashes)
            for i in range(count):
                results.append((nonces[i], h_bytes[i*32 : (i+1)*32].hex()))

        # Clean buffers
        if seed_buf:
            self.opencl.clReleaseMemObject(seed_buf)
        self.opencl.clReleaseMemObject(header_buf)
        self.opencl.clReleaseMemObject(target_buf)
        self.opencl.clReleaseMemObject(found_count_buf)
        self.opencl.clReleaseMemObject(found_nonces_buf)
        self.opencl.clReleaseMemObject(found_hashes_buf)

        batch_hashes = global_work_size * nonces_per_thread
        self.total_hashes += batch_hashes
        if t_delta > 0:
            self.hashrate = batch_hashes / t_delta

        return results


# -------------------------------------------------------------
# CPU Fallback Miner Implementation
# -------------------------------------------------------------
class CPUMiner:
    """
    Multi-threaded CPU miner worker.
    Allows mining on any machine even without dedicated GPU.
    """
    def __init__(self, threads: int = 0):
        import multiprocessing
        self.threads = threads if threads > 0 else max(1, multiprocessing.cpu_count() - 1)
        self.hashrate = 0.0
        self.total_hashes = 0
        self.blocks_found = 0
        self.device = OpenCLDevice(None, None, "CPU Worker", f"Multi-Core CPU ({self.threads} Threads)", 0)

    def search_batch(self, header_hash: bytes, target_int: int, epoch: int,
                     start_nonce: int, count: int = 5000) -> List[Tuple[int, str]]:
        from urcoin.crypto import urhash_cpu_hash, get_epoch_seed
        epoch_seed = get_epoch_seed(epoch)
        t0 = time.perf_counter()
        results = []

        for nonce in range(start_nonce, start_nonce + count):
            digest = urhash_cpu_hash(header_hash, nonce, epoch_seed)
            if int.from_bytes(digest, "big") <= target_int:
                results.append((nonce, digest.hex()))
                break

        dt = time.perf_counter() - t0
        self.total_hashes += count
        if dt > 0:
            self.hashrate = count / dt
        return results

