#pragma once

#include <iostream>
#include <cmath>

namespace complex_numbers {

class Complex {
public:
    Complex(double real, double imaginary);
    Complex operator+(const Complex& other) const;
    Complex operator-(const Complex& other) const;
    Complex operator*(const Complex& other) const;
    Complex operator/(const Complex& other) const;
    double abs() const;
    Complex conj() const;
    double real() const;
    double imag() const;
    Complex exp() const;
};

bool operator==(const Complex& lhs, const Complex& rhs);
std::ostream& operator<<(std::ostream& os, Complex const& value);
Complex operator+(const Complex& complex, double scalar);
Complex operator+(double scalar, const Complex& complex);
Complex operator-(const Complex& complex, double scalar);
Complex operator-(double scalar, const Complex& complex);
Complex operator*(const Complex& complex, double scalar);
Complex operator*(double scalar, const Complex& complex);
Complex operator/(const Complex& complex, double scalar);
Complex operator/(double scalar, const Complex& complex);

}  // namespace complex_numbers
