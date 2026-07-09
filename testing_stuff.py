from collections import namedtuple
import asyncio

Employee = namedtuple('Employee', ['name', 'role'])

def get_department_data():
    """ returns a dictionary with 3 keys and the values
    are lists of employee tuples"""

    return {
        'Engineering': [
            Employee(name='alice', role='eng'),
            Employee(name='sachin', role='architect')
        ],
        'Sales': [
            Employee(name='ashish', role='fsm'),
            Employee(name='ashish', role='fsm'),
        ],
        'Support': [
            Employee(name='sam', role='dpo'),
            Employee(name='sam', role='dpo'),
        ],
    }

def extract_unique_name(employee_dict) -> set:
    unique_names = set()

    for employee_name in employee_dict.values():
        for item in employee_name:
            unique_names.add(item.name)

    return unique_names


def get_names():
    my_data = get_department_data()
    set_of_names = extract_unique_name(my_data)
    print(set_of_names)

if __name__ == "__main__":
    get_names()


