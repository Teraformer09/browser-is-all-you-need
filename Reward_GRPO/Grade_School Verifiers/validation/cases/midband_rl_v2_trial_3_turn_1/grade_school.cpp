#include "grade_school.h"

#include <algorithm>
#include <utility>

namespace grade_school {

school::school() = default;

const std::map<int, std::vector<std::string>>& school::roster() const {
    return roster_;
}

void school::add(std::string const& name, int grade) {
    if (std::find_if(
            roster_.begin(), roster_.end(),
            [&](const std::pair<int, std::vector<std::string>>& entry) {
                return std::find(entry.second.begin(), entry.second.end(), name) !=
                       entry.second.end();
            }) != roster_.end()) {
        throw std::domain_error("student already enrolled");
    }

    auto& names = roster_[grade];
    const auto found =
        std::lower_bound(names.begin(), names.end(), name);
    names.insert(found, name);
}

std::vector<std::string> school::grade(int grade) const {
    const auto found = roster_.find(grade);
    if (found == roster_.end()) {
        return {};
    }
    return found->second;
}

}  // namespace grade_school
