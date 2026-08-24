#include "clock.h"

#include <iomanip>
#include <sstream>

namespace date_independent {

clock::clock(int minutes) : minutes_(minutes) {}

clock clock::at(int hour, int minute) {
    const int minutes_per_hour = 60;
    const int minutes_per_day = minutes_per_hour * 24;
    int minutes = hour * minutes_per_hour + minute;
    minutes = minutes % minutes_per_day;
    if (minutes < 0) {
        minutes += minutes_per_day;
    }
    return clock(minutes);
}

clock& clock::plus(int minutes) {
    minutes_ += minutes;
    minutes_ %= (60 * 24);
    if (minutes_ < 0) {
        minutes_ += 60 * 24;
    }
    return *this;
}

clock& clock::minus(int minutes) {
    minutes_ -= minutes;
    minutes_ %= (60 * 24);
    if (minutes_ < 0) {
        minutes_ += 60 * 24;
    }
    return *this;
}

clock::operator std::string() const {
    std::ostringstream output;
    output << std::setfill('0') << std::setw(2) << minutes_ / 60 << ':'
           << std::setw(2) << minutes_ % 60;
    return output.str();
}

bool clock::operator==(const clock& rhs) const {
    return minutes_ == rhs.minutes_;
}

bool operator!=(const clock& lhs, const clock& rhs) {
    return !(lhs == rhs);
}

}  // namespace date_independent
