#include "clock.h"

#include <iomanip>
#include <sstream>

namespace date_independent {

clock::clock(int minutes) : minutes_(minutes) {}

clock clock::at(int hour, int minute) {
    const int total_minutes = hour * 60 + minute;
    const int wrapped_minutes = (total_minutes % 1440 + 1440) % 1440;
    return clock(wrapped_minutes);
}

clock& clock::plus(int minutes) {
    minutes_ += minutes;
    minutes_ = (minutes_ % 1440 + 1440) % 1440;
    return *this;
}

clock& clock::minus(int minutes) {
    minutes_ -= minutes;
    minutes_ = (minutes_ % 1440 + 1440) % 1440;
    return *this;
}

clock::operator std::string() const {
    std::ostringstream output;
    output << std::setfill('0') << std::setw(2) << minutes_ / 60 << ':' << std::setw(2) << minutes_ % 60;
    return output.str();
}

bool clock::operator==(const clock& rhs) const {
    return minutes_ == rhs.minutes_;
}

bool operator!=(const clock& lhs, const clock& rhs) {
    return !(lhs == rhs);
}

}  // namespace date_independent
