#pragma once

#include <cmath>
#include <iostream>

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

    friend bool operator==(const Complex& lhs, const Complex& rhs);
    friend std::ostream& operator<<(std::ostream& os, Complex const& value);

private:
    double real_;
    double imaginary_;
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
