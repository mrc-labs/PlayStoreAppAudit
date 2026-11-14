// Native R08 prerequisite; no Qt GUI or packaged-application acceptance.
#include <hb.h>
#include <hb-ot.h>
#include <md4c.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>

static void require(bool value, const char *message) {
    if (!value) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}
static void shape(const char *path, unsigned expected) {
    hb_blob_t *blob = hb_blob_create_from_file_or_fail(path);
    require(blob != nullptr, "Font input unavailable");
    hb_face_t *face = hb_face_create(blob, 0);
    require(hb_face_get_glyph_count(face) > 0, "Font has no glyphs");
    hb_font_t *font = hb_font_create(face);
    hb_ot_font_set_funcs(font);
    hb_buffer_t *buffer = hb_buffer_create();
    hb_buffer_add_utf8(buffer, "fi", 2, 0, 2);
    hb_buffer_guess_segment_properties(buffer);
    hb_shape(font, buffer, nullptr, 0);
    unsigned count = 0;
    const auto *glyphs = hb_buffer_get_glyph_infos(buffer, &count);
    require(count == expected, "OpenType ligature regression");
    const auto *positions = hb_buffer_get_glyph_positions(buffer, &count);
    for (unsigned i = 0; i < count; ++i) {
        require(glyphs[i].codepoint != 0 && positions[i].x_advance > 0, "Missing glyph/advance");
    }
    hb_buffer_destroy(buffer); hb_font_destroy(font); hb_face_destroy(face); hb_blob_destroy(blob);
}
struct MarkdownState { unsigned headings = 0, strong = 0, links = 0, text = 0; bool cancel = false; };
static int enterBlock(MD_BLOCKTYPE type, void *, void *data) {
    auto *state = static_cast<MarkdownState *>(data);
    if (state->cancel) return 17;
    if (type == MD_BLOCK_H) ++state->headings;
    return 0;
}
static int leaveBlock(MD_BLOCKTYPE, void *, void *) { return 0; }
static int enterSpan(MD_SPANTYPE type, void *, void *data) {
    auto *state = static_cast<MarkdownState *>(data);
    if (type == MD_SPAN_STRONG) ++state->strong;
    if (type == MD_SPAN_A) ++state->links;
    return 0;
}
static int leaveSpan(MD_SPANTYPE, void *, void *) { return 0; }
static int text(MD_TEXTTYPE, const MD_CHAR *, MD_SIZE size, void *data) {
    static_cast<MarkdownState *>(data)->text += size; return 0;
}
int main(int argc, char **argv) {
    require(argc == 3, "Two original test fonts required");
    require(std::strcmp(hb_version_string(), "15.1.0") == 0, "Wrong loaded HarfBuzz");
    shape(argv[1], 1); shape(argv[2], 2);
    MD_PARSER parser{};
    parser.abi_version = 0; parser.flags = MD_DIALECT_COMMONMARK;
    parser.enter_block = enterBlock; parser.leave_block = leaveBlock;
    parser.enter_span = enterSpan; parser.leave_span = leaveSpan; parser.text = text;
    const char markdown[] = "# Heading\n\n**bold** and [link](https://example.com) with UTF-8 \xc3\xa8.\n";
    MarkdownState state;
    require(md_parse(markdown, sizeof(markdown) - 1, &parser, &state) == 0, "Markdown parse failed");
    require(state.headings == 1 && state.strong == 1 && state.links == 1 && state.text > 10, "Markdown callback regression");
    state.cancel = true;
    require(md_parse(markdown, sizeof(markdown) - 1, &parser, &state) == 17, "Markdown callback cancellation lost");
    std::cout << "PASS HarfBuzz15.1.0 OpenType liga/no-liga and MD4C0.6 heading/strong/link/UTF8/callback cancellation\n";
    std::ifstream maps("/proc/self/maps"); std::cout << maps.rdbuf();
}
