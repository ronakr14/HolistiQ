def add_numbers(a, b):
    return a + b


def main():
    x = 5
    y = 10  #  fixed: int instead of string
    result = add_numbers(x, y)
    for i in range(10):
        print("Loop:", i)
    print("Result:", result)
    names = ["Ronak", "Alex", "Sam"]


if __name__ == "__main__":
    main()