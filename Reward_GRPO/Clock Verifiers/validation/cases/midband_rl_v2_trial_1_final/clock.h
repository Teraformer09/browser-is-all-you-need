#pragma once

#include <string>
#include <iomanip>
#include <sstream>

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
    int minutes_of_day() const;
};

bool operator!=(const clock& lhs, const clock& rhs);

inline int clock::minutes_of_day() const {
    int minutes = minutes_ % (24 * 60);
    if (minutes < 0) minutes += 24 * 60;
    return minutes;
}

inline bool clock::operator==(const clock& rhs) const {
    return minutes_ == rhs.minutes_;
}

inline bool operator!=(const clock& lhs, const clock& rhs) {
    return !(lhs == rhs);
}

inline clock::operator std::string() const {
    std::ostringstream output;
    int minutes = minutes_of_day();
    output << std::setfill('0') << std::setw(2) << minutes / 60 << ':'
           << std::setw(2) << minutes % 60;
    return output.str();
}

}  // namespace date_independent
