#include "grade_school.h"

#include <algorithm>
#include <stdexcept>

namespace grade_school {

const std::map<int, std::vector<std::string>>& school::roster() const {
    return roster_;
}

void school::add(std::string const& name, int grade) {
    auto& names = roster_[grade];
    const auto found =
        std::find(names.begin(), names.end(), name);
    if (found != names.end()) {
        throw std::invalid_argument("student already exists");
    }
    names.push_back(name);
    std::sort(names.begin(), names.end());
}

std::vector<std::string> school::grade(int grade) const {
    const auto found = roster_.find(grade);
    if (found == roster_.end()) {
        return {};
    }
    std::vector<std::string> result = found->second;
    std::sort(result.begin(), result.end());
    return result;
}

}  // namespace grade_school
