#pragma once

#include <string>

namespace date_independent {

class clock {
public:
    static clock at(int hour, int minute = 0);
    clock& plus(int minutes);
    clock& minus(int minutes);
    operator std::string() const;
    bool operator==(const clock& rhs) const;

private:
    explicit clock(int minutes);
    int minutes_;
};

bool operator!=(const clock& lhs, const clock& rhs);

}  // namespace date_independent
