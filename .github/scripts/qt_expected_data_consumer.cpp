#include "qexpected_p.h"
#include <cstdlib>
#include <memory>

static_assert(Q23_TL_EXPECTED_VERSION_MAJOR == 1 && Q23_TL_EXPECTED_VERSION_MINOR == 3
              && Q23_TL_EXPECTED_VERSION_PATCH == 1, "Controlled expected1.3.1 header required");

int main(int argc, char **)
{
    q23::expected<int, int> good(21);
    q23::expected<int, int> bad(q23::unexpected(7));
    if (argc > 1) {
        std::set_terminate([] { std::_Exit(86); });
        return bad.value();
    }
    if (!good || good.value() != 21 || bad || bad.error() != 7)
        return 1;
    auto mapped = good.map([](int value) { return value * 2; });
    auto chained = mapped.and_then([](int value) { return q23::expected<int, int>(value + 1); });
    if (!chained || *chained != 43 || bad.map_error([](int value) { return value + 1; }).error() != 8)
        return 2;
    q23::expected<std::unique_ptr<int>, int> movable(std::make_unique<int>(5));
    auto moved = std::move(movable);
    if (**moved != 5)
        return 3;
    q23::expected<void, int> empty;
    if (!empty)
        return 4;
    q23::expected<void, int> voidError(q23::unexpected(9));
    if (voidError || voidError.error() != 9)
        return 7;
#ifndef QT_NO_EXCEPTIONS
    try {
        bad.value();
        return 5;
    } catch (const q23::bad_expected_access<int> &error) {
        if (error.error() != 7)
            return 6;
    }
#endif
    return 0;
}
