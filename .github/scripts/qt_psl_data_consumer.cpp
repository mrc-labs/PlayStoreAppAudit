#include <fstream>
#include <iostream>
#include <string>

// Include directories select only the guarded Qt copies in the private source tree.
#include "psl_data.cpp"
#include "lookup_string_in_fixed_set.c"

int main(int argc, char **argv)
{
    if (argc != 2 || !GetUtfMode(kDafsa, sizeof(kDafsa)))
        return 1;
    std::ifstream fixture(argv[1], std::ios::binary);
    if (!fixture)
        return 2;
    std::string line;
    unsigned count = 0;
    while (std::getline(fixture, line)) {
        const auto tab = line.find('\t');
        if (tab == std::string::npos)
            return 3;
        const auto key = line.substr(tab + 1);
        const int expected = std::stoi(line.substr(0, tab));
        const int actual = LookupStringInFixedSet(kDafsa, sizeof(kDafsa), key.data(), key.size());
        if (actual != expected) {
            std::cerr << "PSL mismatch " << key << ": " << actual << " != " << expected << '\n';
            return 4;
        }
        ++count;
    }
    // This low-level lookup consumes nonempty domain keys. Empty-domain policy
    // belongs to the Qt caller, rather than the DAFSA metadata sentinel.
    for (const std::string key : {"psaa-no-such-suffix.invalid", "unregistered.psaa.invalid", "not-a-tld.example.invalid"}) {
        if (LookupStringInFixedSet(kDafsa, sizeof(kDafsa), key.data(), key.size()) != -1) {
            std::cerr << "Unexpected suffix match: " << key << '\n';
            return 5;
        }
    }
    if (count < 10000)
        return 6;
    std::cout << "PASS " << count << " PSL UTF8/IDNA rules, flags and missing-domain negatives\n";
}
