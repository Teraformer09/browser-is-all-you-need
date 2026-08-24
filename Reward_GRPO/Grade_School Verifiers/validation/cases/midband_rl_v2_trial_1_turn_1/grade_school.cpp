#include "grade_school.h"

#include <algorithm>
#include <stdexcept>

namespace grade_school {

const std::map<int, std::vector<std::string>>& school::roster() const {
    return roster_;
}

void school::add(std::string const& name, int grade) {
    for (const auto& [g, students] : roster_) {
        const auto found = std::find(students.begin(), students.end(), name);
        if (found != students.end()) {
            if (g == grade) {
                throw std::runtime_error("Student already in this grade");
            }
            roster_[g].erase(found);
            break;
        }
    }
    roster_[grade].push_back(name);
    std::sort(roster_[grade].begin(), roster_[grade].end());
}

std::vector<std::string> school::grade(int grade) const {
    const auto found = roster_.find(grade);
    if (found == roster_.end()) {
        return {};
    }
    return found->second;
}

}  // namespace grade_school
