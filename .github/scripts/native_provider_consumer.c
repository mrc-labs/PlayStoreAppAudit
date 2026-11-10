#include <ffi.h>
#include <lzma.h>
#include <mpdecimal.h>
#include <sqlite3.h>
#include <zlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

static int64_t add(int64_t a, int64_t b) { return a + b; }
static void callback(ffi_cif *cif, void *result, void **args, void *data) {
    (void)cif;
    *(int64_t *)result = *(int64_t *)args[0] + *(int64_t *)args[1] + *(int64_t *)data;
}
static double mixed(int base, ...) {
    va_list args;
    va_start(args, base);
    const char *text = va_arg(args, const char *);
    int integer = va_arg(args, int);
    double real = va_arg(args, double);
    va_end(args);
    return base + strlen(text) + integer + real;
}
int main(void) {
    sqlite3 *db = NULL;
    sqlite3_stmt *query = NULL;
    if (sqlite3_open(":memory:", &db) != SQLITE_OK) return 1;
    if (sqlite3_prepare_v2(db, "select 21*2", -1, &query, NULL) != SQLITE_OK) return 2;
    if (sqlite3_step(query) != SQLITE_ROW || sqlite3_column_int(query, 0) != 42) return 3;
    sqlite3_finalize(query);
    sqlite3_close(db);
    const unsigned char input[] = "controlled native codec roundtrip";
    unsigned char encoded[256], decoded[256];
    uLongf compressed = sizeof(encoded), plain = sizeof(decoded);
    if (compress(encoded, &compressed, input, sizeof(input)) != Z_OK) return 4;
    if (uncompress(decoded, &plain, encoded, compressed) != Z_OK || plain != sizeof(input) || memcmp(decoded, input, plain)) return 5;
    size_t written = 0, consumed = 0, expanded = 0;
    uint64_t limit = UINT64_MAX;
    if (lzma_easy_buffer_encode(6, LZMA_CHECK_CRC64, NULL, input, sizeof(input), encoded, &written, sizeof(encoded)) != LZMA_OK) return 6;
    if (lzma_stream_buffer_decode(&limit, 0, NULL, encoded, &consumed, written, decoded, &expanded, sizeof(decoded)) != LZMA_OK
        || expanded != sizeof(input) || consumed != written || memcmp(decoded, input, expanded)) return 7;
    ffi_cif cif;
    int64_t a = 11, b = 31, result = 0, extra = 3;
    ffi_type *types[] = {&ffi_type_sint64, &ffi_type_sint64};
    void *args[] = {&a, &b}, *code = NULL;
    if (ffi_prep_cif(&cif, FFI_DEFAULT_ABI, 2, &ffi_type_sint64, types) != FFI_OK) return 8;
    ffi_call(&cif, FFI_FN(add), &result, args);
    if (result != 42) return 9;
    ffi_closure *closure = ffi_closure_alloc(sizeof(ffi_closure), &code);
    if (!closure || ffi_prep_closure_loc(closure, &cif, callback, &extra, code) != FFI_OK) return 10;
    int64_t (*call)(int64_t, int64_t) = (int64_t (*)(int64_t, int64_t))code;
    if (call(a, b) != 45) return 11;
    ffi_closure_free(closure);
    int fixed = 7, integer = 13;
    const char *text = "ffi";
    double real = 4.5, total = 0;
    ffi_type *mixed_types[] = {&ffi_type_sint, &ffi_type_pointer, &ffi_type_sint, &ffi_type_double};
    void *mixed_args[] = {&fixed, &text, &integer, &real};
    if (ffi_prep_cif_var(&cif, FFI_DEFAULT_ABI, 1, 4, &ffi_type_double, mixed_types) != FFI_OK) return 12;
    ffi_call(&cif, FFI_FN(mixed), &total, mixed_args);
    if (total != 27.5) return 13;
    printf("{\"sqlite\":\"%s\",\"libmpdec\":\"%s\",\"libffi\":\"%s\",\"liblzma\":\"%s\",\"zlib\":\"%s\",\"mixed\":%.1f,\"calls\":\"SQL/codec/callback PASS\"}\n",
           sqlite3_libversion(), mpd_version(), ffi_get_version(), lzma_version_string(), zlibVersion(), total);
    return 0;
}
