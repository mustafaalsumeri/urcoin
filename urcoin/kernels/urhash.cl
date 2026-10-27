// Ur Coin (URC) - UrHash OpenCL Kernel
// High-Performance Memory-Hard Proof-of-Work tailored for 3GB-6GB VRAM GPUs

#define ROTR64(x, y) (((x) >> (y)) ^ ((x) << (64 - (y))))
#define ROTR32(x, y) (((x) >> (y)) ^ ((x) << (32 - (y))))

// -------------------------------------------------------------
// BLAKE2b Constants & Round Function
// -------------------------------------------------------------
#define G(v, m, a, b, c, d, x, y) { \
    v[a] = v[a] + v[b] + m[x]; \
    v[d] = ROTR64(v[d] ^ v[a], 32); \
    v[c] = v[c] + v[d]; \
    v[b] = ROTR64(v[b] ^ v[c], 24); \
    v[a] = v[a] + v[b] + m[y]; \
    v[d] = ROTR64(v[d] ^ v[a], 16); \
    v[c] = v[c] + v[d]; \
    v[b] = ROTR64(v[b] ^ v[c], 63); \
}

__constant ulong BLAKE2B_IV[8] = {
    0x6a09e667f3bcc908UL, 0xbb67ae8584caa73bUL,
    0x3c6ef372fe94f82bUL, 0xa54ff53a5f1d36f1UL,
    0x510e527fade682d1UL, 0x9b05688c2b3e6c1fUL,
    0x1f83d9abfb41bd6bUL, 0x5be0cd19137e2179UL
};

__constant uchar SIGMA[12][16] = {
    {  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15 },
    { 14, 10,  4,  8,  9, 15, 13,  6,  1, 12,  0,  2, 11,  7,  5,  3 },
    { 11,  8, 12,  0,  5,  2, 15, 13, 10, 14,  3,  6,  7,  1,  9,  4 },
    {  7,  9,  3,  1, 13, 12, 11, 14,  2,  6,  5, 10,  4,  0, 15,  8 },
    {  9,  0,  5,  7,  2,  4, 10, 15, 14,  1, 11, 12,  6,  8,  3, 13 },
    {  2, 12,  6, 10,  0, 11,  8,  3,  4, 13,  7,  5, 15, 14,  1,  9 },
    { 12,  5,  1, 15, 14, 13,  4, 10,  0,  7,  6,  3,  9,  2,  8, 11 },
    { 13, 11,  7, 14, 12,  1,  3,  9,  5,  0, 15,  4,  8,  6,  2, 10 },
    {  6, 15, 14,  9, 11,  3,  0,  8, 12,  2, 13,  7,  1,  4, 10,  5 },
    { 10,  2,  8,  4,  7,  6,  1,  5, 15, 11,  9, 14,  3, 12, 13,  0 },
    {  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15 },
    { 14, 10,  4,  8,  9, 15, 13,  6,  1, 12,  0,  2, 11,  7,  5,  3 }
};

// Compress 40 bytes: (32 bytes input + 8 bytes uint64 index/nonce) -> 64 bytes output
void blake2b_compress_40(const ulong* in32, ulong idx, ulong* out64) {
    ulong m[16];
    m[0] = in32[0];
    m[1] = in32[1];
    m[2] = in32[2];
    m[3] = in32[3];
    m[4] = idx;
    for (int i = 5; i < 16; i++) m[i] = 0UL;

    ulong v[16];
    for (int i = 0; i < 8; i++) v[i] = BLAKE2B_IV[i];
    v[0] ^= 0x01010040UL;
    for (int i = 0; i < 8; i++) v[8 + i] = BLAKE2B_IV[i];
    v[12] ^= 40UL;
    v[14] ^= 0xFFFFFFFFFFFFFFFFUL;

    for (int r = 0; r < 12; r++) {
        G(v, m, 0, 4,  8, 12, SIGMA[r][ 0], SIGMA[r][ 1]);
        G(v, m, 1, 5,  9, 13, SIGMA[r][ 2], SIGMA[r][ 3]);
        G(v, m, 2, 6, 10, 14, SIGMA[r][ 4], SIGMA[r][ 5]);
        G(v, m, 3, 7, 11, 15, SIGMA[r][ 6], SIGMA[r][ 7]);
        G(v, m, 0, 5, 10, 15, SIGMA[r][ 8], SIGMA[r][ 9]);
        G(v, m, 1, 6, 11, 12, SIGMA[r][10], SIGMA[r][11]);
        G(v, m, 2, 7,  8, 13, SIGMA[r][12], SIGMA[r][13]);
        G(v, m, 3, 4,  9, 14, SIGMA[r][14], SIGMA[r][15]);
    }

    ulong h[8];
    for (int i = 0; i < 8; i++) h[i] = BLAKE2B_IV[i];
    h[0] ^= 0x01010040UL;

    for (int i = 0; i < 8; i++) {
        out64[i] = h[i] ^ v[i] ^ v[8 + i];
    }
}

// -------------------------------------------------------------
// SHA-256 for 64-byte input (Finalizer)
// -------------------------------------------------------------
__constant uint K256[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTR32(x, 2) ^ ROTR32(x, 13) ^ ROTR32(x, 22))
#define EP1(x) (ROTR32(x, 6) ^ ROTR32(x, 11) ^ ROTR32(x, 25))
#define SIG0(x) (ROTR32(x, 7) ^ ROTR32(x, 18) ^ ((x) >> 3))
#define SIG1(x) (ROTR32(x, 17) ^ ROTR32(x, 19) ^ ((x) >> 10))

void sha256_compress_64bytes(const ulong* in64, uchar* out32) {
    const uchar* byte_in = (const uchar*)in64;
    uint w[64];
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint)byte_in[i*4] << 24) | ((uint)byte_in[i*4 + 1] << 16) |
               ((uint)byte_in[i*4 + 2] << 8) | ((uint)byte_in[i*4 + 3]);
    }
    
    uint a = 0x6a09e667, b = 0xbb67ae85, c = 0x3c6ef372, d = 0xa54ff53a;
    uint e = 0x510e527f, f = 0x9b05688c, g = 0x1f83d9ab, h = 0x5be0cd19;

    for (int i = 16; i < 64; i++) {
        w[i] = SIG1(w[i - 2]) + w[i - 7] + SIG0(w[i - 15]) + w[i - 16];
    }

    for (int i = 0; i < 64; i++) {
        uint t1 = h + EP1(e) + CH(e, f, g) + K256[i] + w[i];
        uint t2 = EP0(a) + MAJ(a, b, c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }

    a += 0x6a09e667; b += 0xbb67ae85; c += 0x3c6ef372; d += 0xa54ff53a;
    e += 0x510e527f; f += 0x9b05688c; g += 0x1f83d9ab; h += 0x5be0cd19;

    for (int i = 0; i < 64; i++) w[i] = 0;
    w[0] = 0x80000000;
    w[15] = 512;

    for (int i = 16; i < 64; i++) {
        w[i] = SIG1(w[i - 2]) + w[i - 7] + SIG0(w[i - 15]) + w[i - 16];
    }

    uint a2 = a, b2 = b, c2 = c, d2 = d, e2 = e, f2 = f, g2 = g, h2 = h;
    for (int i = 0; i < 64; i++) {
        uint t1 = h2 + EP1(e2) + CH(e2, f2, g2) + K256[i] + w[i];
        uint t2 = EP0(a2) + MAJ(a2, b2, c2);
        h2 = g2; g2 = f2; f2 = e2; e2 = d2 + t1;
        d2 = c2; c2 = b2; b2 = a2; a2 = t1 + t2;
    }

    a += a2; b += b2; c += c2; d += d2; e += e2; f += f2; g += g2; h += h2;

    uint state[8] = {a, b, c, d, e, f, g, h};
    for (int i = 0; i < 8; i++) {
        out32[i*4 + 0] = (state[i] >> 24) & 0xFF;
        out32[i*4 + 1] = (state[i] >> 16) & 0xFF;
        out32[i*4 + 2] = (state[i] >> 8)  & 0xFF;
        out32[i*4 + 3] = state[i] & 0xFF;
    }
}

// Compare 32-byte big-endian hash with target: returns true if hash <= target
bool check_hash_target(const uchar* hash32, __global const uchar* target32) {
    for (int i = 0; i < 32; i++) {
        if (hash32[i] < target32[i]) return true;
        if (hash32[i] > target32[i]) return false;
    }
    return true; // equal
}

// -------------------------------------------------------------
// Kernel 1: Parallel DAG Buffer Generation
// -------------------------------------------------------------
__kernel void generate_dag_buffer(
    __global const ulong* epoch_seed_in,
    ulong num_items,
    __global ulong* dag_out
) {
    ulong idx = get_global_id(0);
    if (idx >= num_items) return;

    ulong seed[4];
    seed[0] = epoch_seed_in[0];
    seed[1] = epoch_seed_in[1];
    seed[2] = epoch_seed_in[2];
    seed[3] = epoch_seed_in[3];

    ulong item[8];
    blake2b_compress_40(seed, idx, item);

    ulong base = idx * 8;
    for (int j = 0; j < 8; j++) {
        dag_out[base + j] = item[j];
    }
}

// -------------------------------------------------------------
// Kernel 2: Parallel GPU PoW Miner (Batch Search)
// -------------------------------------------------------------
__kernel void urhash_miner_search(
    __global const ulong* dag,
    __global const ulong* header_hash_in,
    __global const uchar* target32,
    ulong start_nonce,
    ulong nonces_per_thread,
    ulong num_items,
    int rounds,
    volatile __global uint* found_count,
    __global ulong* found_nonces,
    __global uchar* found_hashes
) {
    ulong tid = get_global_id(0);
    ulong base_nonce = start_nonce + (tid * nonces_per_thread);

    ulong header[4];
    header[0] = header_hash_in[0];
    header[1] = header_hash_in[1];
    header[2] = header_hash_in[2];
    header[3] = header_hash_in[3];

    for (ulong step = 0; step < nonces_per_thread; step++) {
        // If another thread found enough solutions, stop early
        if (*found_count >= 16) return;

        ulong current_nonce = base_nonce + step;
        ulong s[8];
        blake2b_compress_40(header, current_nonce, s);

        for (int r = 0; r < rounds; r++) {
            ulong idx = (s[0] ^ s[r % 8] ^ ((ulong)r * 0x9E3779B97F4A7C15UL)) % num_items;
            ulong base = idx * 8;
            for (int j = 0; j < 8; j++) {
                ulong dag_val = dag[base + j];
                s[j] = (ROTR64(s[j] ^ dag_val, 17) * 0x100000001b3UL) + (ulong)r;
            }
        }

        uchar final_hash[32];
        sha256_compress_64bytes(s, final_hash);

        if (check_hash_target(final_hash, target32)) {
            // Found a valid Proof-of-Work!
            uint slot = atomic_inc(found_count);
            if (slot < 16) {
                found_nonces[slot] = current_nonce;
                for (int b = 0; b < 32; b++) {
                    found_hashes[slot * 32 + b] = final_hash[b];
                }
            }
            return;
        }
    }
}

// -------------------------------------------------------------
// Kernel 3: Zero-VRAM Light GPU PoW Miner (For Weak / Low-VRAM GPUs)
// Computes DAG lines on-the-fly without requiring 1.0 GB allocation in VRAM!
// -------------------------------------------------------------
__kernel void urhash_miner_search_light(
    __global const ulong* epoch_seed_in,
    __global const ulong* header_hash_in,
    __global const uchar* target32,
    ulong start_nonce,
    ulong nonces_per_thread,
    ulong num_items,
    int rounds,
    volatile __global uint* found_count,
    __global ulong* found_nonces,
    __global uchar* found_hashes
) {
    ulong tid = get_global_id(0);
    ulong base_nonce = start_nonce + (tid * nonces_per_thread);

    ulong epoch_seed[4];
    epoch_seed[0] = epoch_seed_in[0];
    epoch_seed[1] = epoch_seed_in[1];
    epoch_seed[2] = epoch_seed_in[2];
    epoch_seed[3] = epoch_seed_in[3];

    ulong header[4];
    header[0] = header_hash_in[0];
    header[1] = header_hash_in[1];
    header[2] = header_hash_in[2];
    header[3] = header_hash_in[3];

    for (ulong step = 0; step < nonces_per_thread; step++) {
        if (*found_count >= 16) return;

        ulong current_nonce = base_nonce + step;
        ulong s[8];
        blake2b_compress_40(header, current_nonce, s);

        for (int r = 0; r < rounds; r++) {
            ulong idx = (s[0] ^ s[r % 8] ^ ((ulong)r * 0x9E3779B97F4A7C15UL)) % num_items;
            ulong dag_item[8];
            blake2b_compress_40(epoch_seed, idx, dag_item);
            for (int j = 0; j < 8; j++) {
                s[j] = (ROTR64(s[j] ^ dag_item[j], 17) * 0x100000001b3UL) + (ulong)r;
            }
        }

        uchar final_hash[32];
        sha256_compress_64bytes(s, final_hash);

        if (check_hash_target(final_hash, target32)) {
            uint slot = atomic_inc(found_count);
            if (slot < 16) {
                found_nonces[slot] = current_nonce;
                for (int b = 0; b < 32; b++) {
                    found_hashes[slot * 32 + b] = final_hash[b];
                }
            }
            return;
        }
    }
}

