// Cheap flag-policy prerequisite. Generated constants/expression come from hash-guarded Qt source.
#include "qt-md4c-reviewed-flags.h"
#include <md4c.h>
#include <cstdlib>
#include <iostream>
#include <string>

static void require(bool ok, const char *message) {
    if (!ok) { std::cerr << message << '\n'; std::exit(1); }
}
struct State { unsigned footnotes = 0, admonitions = 0, tables = 0, strike = 0, tasks = 0, links = 0; std::string text; };
static int block(MD_BLOCKTYPE type, void *detail, void *data) {
    auto &s = *static_cast<State *>(data);
    if (type == MD_BLOCK_FOOTNOTE_DEF) ++s.footnotes;
    if (type == MD_BLOCK_ADMONITION) ++s.admonitions;
    if (type == MD_BLOCK_TABLE) ++s.tables;
    if (type == MD_BLOCK_LI && static_cast<MD_BLOCK_LI_DETAIL *>(detail)->is_task) ++s.tasks;
    return 0;
}
static int leaveBlock(MD_BLOCKTYPE, void *, void *) { return 0; }
static int span(MD_SPANTYPE type, void *, void *data) {
    auto &s = *static_cast<State *>(data);
    if (type == MD_SPAN_FOOTNOTE_REF) ++s.footnotes;
    if (type == MD_SPAN_DEL) ++s.strike;
    if (type == MD_SPAN_A) ++s.links;
    return 0;
}
static int leaveSpan(MD_SPANTYPE, void *, void *) { return 0; }
static int text(MD_TEXTTYPE, const MD_CHAR *value, MD_SIZE size, void *data) {
    static_cast<State *>(data)->text.append(value, size); return 0;
}
static State parse(unsigned flags, const std::string &value) {
    MD_PARSER p{}; p.flags = flags;
    p.enter_block = block; p.leave_block = leaveBlock;
    p.enter_span = span; p.leave_span = leaveSpan; p.text = text;
    State result;
    require(md_parse(value.data(), MD_SIZE(value.size()), &p, &result) == 0, "Parser failed");
    return result;
}
int main() {
    constexpr unsigned legacy = MD_FLAG_PERMISSIVEAUTOLINKS | MD_FLAG_TABLES | MD_FLAG_STRIKETHROUGH
        | MD_FLAG_TASKLISTS | MD_FLAG_UNDERLINE;
    static_assert(qtDialectGitHub == (legacy | FeatureFrontMatter));
    require(qtProviderFlags(qtDialectGitHub) == legacy, "Qt public flags changed");
    require(qtProviderFlags(0) == 0, "CommonMark changed");
    const std::string reference = "before[^n]\n\n[^n]: after\n";
    require(parse(qtDialectGitHub, reference).footnotes > 0, "Original bit collision not demonstrated");
    const auto mapped = parse(qtProviderFlags(qtDialectGitHub), reference);
    require(mapped.footnotes == 0 && mapped.links == 1 && mapped.text == "before^n", "Legacy reference changed");
    require(parse(qtProviderFlags(qtDialectGitHub), "> [!NOTE]\n> note body\n").admonitions == 0,
        "New admonitions implicitly enabled");
    const auto gfm = parse(qtProviderFlags(qtDialectGitHub),
        "- [x] done\n- [ ] todo\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\n~~gone~~\n");
    require(gfm.tasks == 2 && gfm.tables == 1 && gfm.strike == 1, "Existing GitHub features lost");
    std::cout << "PASS original collision/Qt-only mask/CommonMark/reference/no-admonitions/GFM table-task-strike\n";
}
