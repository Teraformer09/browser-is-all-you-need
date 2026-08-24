#include "clock.h"

#include <iomanip>
#include <sstream>

namespace date_independent {

clock::clock(int minutes) : minutes_(minutes) {}

int clock::normalize(int minutes) {
    const int day_minutes = 1440;
    minutes = minutes % day_minutes;
    if (minutes < 0) minutes += day_minutes;
    return minutes;
}

clock clock::at(int hour, int minute) {
    minutes_ = hour * 60 + minute;
    minutes_ = normalize(minutes_);
    return *this;
}

clock& clock::plus(int minutes) {
    minutes_ += minutes;
    minutes_ = normalize(minutes_);
    return *this;
}

clock& clock::minus(int minutes) {
    minutes_ -= minutes;
    minutes_ = normalize(minutes_);
    return *this;
}

clock::operator std::string() const {
    minutes_ = normalize(minutes_);
    std::ostringstream output;
    output << std::setfill('0') << std::setw(2) << minutes_ / 60 << ':' 
           << std::setw(2) << minutes_ % 60;
    return output.str();
}

bool clock::operator==(const clock& rhs) const {
    return normalize(minutes_) == normalize(rhs.minutes_);
}

bool operator!=(const clock& lhs, const clock& rhs) {
    return !(lhs == rhs);
}

}  // namespace date_independent
