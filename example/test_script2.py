import os
from easy_notifier import easy_notifier


@easy_notifier
def main():
    fname = 'test.txt'
    f = open(fname)
    text = f.read()
    f.close()
    print(text)
    return fname


if __name__ == '__main__':
    main()

