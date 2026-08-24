#include "clock.h"

#include <sstream>

namespace date_independent {

clock::clock(int minutes) : minutes_(minutes) {
    minutes_ %= (24 * 60);
    if (minutes_ < 0) minutes_ += 24 * 60;
}

clock clock::at(int hour, int minute) {
    int minutes = hour * 60 + minute;
    minutes %= (24 * 60);
    if (minutes < 0) minutes += 24 * 60;
    return clock(minutes);
}

clock& clock::plus(int minutes) {
    minutes_ += minutes;
    minutes_ %= (24 * 60);
    if (minutes_ < 0) minutes_ += 24 * 60;
    return *this;
}

clock& clock::minus(int minutes) {
    minutes_ -= minutes;
    minutes_ %= (24 * 60);
    if (minutes_ < 0) minutes_ += 24 * 60;
    return *this;
}

clock::operator std::string() const {
    std::ostringstream output;
    int minutes = minutes_of_day();
    output << std::setfill('0') << std::setw(2) << minutes / 60 << ':'
           << std::setw(2) << minutes % 60;
    return output.str();
}

bool clock::operator==(const clock& rhs) const {
    return minutes_ == rhs.minutes_;
}

int clock::minutes_of_day() const {
    int minutes = minutes_ % (24 * 60);
    if (minutes < 0) minutes += 24 * 60;
    return minutes;
}

bool operator!=(const clock& lhs, const clock& rhs) {
    return !(lhs == rhs);
}

}  // namespace date_independent
