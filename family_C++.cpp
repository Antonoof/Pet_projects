#include <iostream>
#include <string>
#include <vector>
using namespace std;

class Person {
    protected:
        string type;
        string name;
        int age;
    public:
        Person(string t, string n, int a) : type(t), name(n), age(a) {}

    virtual void display() const {
    cout << "Type: " << type << ", Name: " << name << ", Age: " << age << endl;
    }

    int getAge() const {
        return age;
    }
};

class Mother : public Person {
    public:
        Mother(string n, int a) : Person("Mother", n, a) {}
};

class Father : public Person {
    public:
        Father(string n, int a) : Person("Father", n, a) {}
};

class Daughter : public Person {
    public:
        Daughter(string n, int a) : Person("Daughter", n, a) {}
};

class Son : public Person {
    public:
        Son(string n, int a) : Person("Son", n, a) {}
};

void displayFamily(const vector<Person*>& family) {
    cout << "Family Members:" << endl;
    for (const auto& member : family) {
        member->display();
    }

    int totalAge = 0;
    for (const auto& member : family) {
        totalAge += member->getAge();
    }

    double averageAge = static_cast<double>(totalAge) / family.size();
    cout << "Average Age: " << averageAge << endl;
}


int main() {
    vector<Person*> family;
    family.push_back(new Mother("Alice", 45));
    family.push_back(new Father("Bob", 48));
    family.push_back(new Daughter("Charlotte", 15));
    family.push_back(new Son("David", 12));

    displayFamily(family);

    // Освобождение памяти
    for (auto& member : family) {
        delete member;
    }

    return 0;
}

