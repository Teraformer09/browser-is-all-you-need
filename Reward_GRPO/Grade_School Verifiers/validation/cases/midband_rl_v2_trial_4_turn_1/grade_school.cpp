#include "grade_school.h"

#include <algorithm>
#include <set>
#include <vector>

namespace grade_school {

const std::map<int, std::vector<std::string>>& school::roster() const {
    return roster_;
}

void school::add(std::string const& name, int grade) {
    if (all_names_.find(name) != all_names_.end()) {
        throw std::invalid_argument("Student already exists");
    }
    auto& names = roster_[grade];
    names.push_back(name);
    std::sort(names.begin(), names.end());
    all_names_.insert(name);
}

std::vector<std::string> school::grade(int grade) const {
    const auto found = roster_.find(grade);
    if (found == roster_.end()) {
        return {};
    }
    return found->second;
}

}  // namespace grade_school
