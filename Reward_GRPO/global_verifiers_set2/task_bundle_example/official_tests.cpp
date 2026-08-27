#include "adder.h"
#include <iostream>
#include <limits>

int main() {
    int passed = 0;
    passed += add(2, 3) == 5;
    passed += add(-4, 1) == -3;
    passed += add(0, 0) == 0;
    std::cout << "tests_passed=" << passed << "/3\n";
    return passed == 3 ? 0 : 1;
}
