// lotsofstuff.cpp

#include <string>
using namespace std;

#include "lotsofstuff.idl"
#include "stdio.h"
#include "iostream"

void func1()
{
    printf("in FUNC1\n");
    return;
}

void func2()
{
    printf("in FUNC2\n");
}

void func3()
{
    printf("in FUNC3\n");
}

int sum(int intArr[10])
{
    int total = 0;
    for (int i = 0; i < 10; i++)
    {
        total += intArr[i];
    }
    return total;
}

int takesTwoArrays(int x[10], int y[10])
{
    int total = 0;
    total += sum(x);
    total += sum(y);
    return total;
}

int showsArraysofArrays(int x[24], int y[24][15], int z[24][15])
{
    int total = 0;
    for (int i = 0; i < 24; i++)
    {
        total += x[i];
        for (int j = 0; j < 15; j++)
        {
            total += y[i][j];
            total += z[i][j];
        }
    }
    return total;
}

string upcase(string s1)
{
    for (auto &c : s1)
        c = toupper(c);

    return s1;
}

Person findPerson(ThreePeople tp)
{
    if (tp.p1.firstname == "John" and tp.p1.lastname == "Doe")
    {
        return tp.p1;
    }
    else if (tp.p2.firstname == "John" and tp.p2.lastname == "Doe")
    {
        return tp.p2;
    }
    else if (tp.p3.firstname == "John" and tp.p3.lastname == "Doe")
    {
        return tp.p3;
    }
    return tp.p1;
}

float multiply(float x, float y)
{
    return x * y;
}

int area(rectangle r)
{
    return r.x * r.y;
}

void searchRectangles(rectangle rects[200])
{

    /* This is a void functon, wso we would just search for the rectangle that has 
        area of 100
    */

    for (int i = 0; i < 200; i++)
    {
        if (area(rects[i]) == 100)
        {
            cout << "Found rectangle with area 100 \n";
            return;
        }
    }

    cout << "No rectangle found\n";
}

int sum_arr(int m1[100])
{
    int result = 0;
    for (int i = 0; i < 100; i++)
    {
        result += m1[i];
    }
    return result;
}

int sum_arr2(int m2[10][100])
{
    int result = 0;
    for (int i = 0; i < 10; i++)
    {
        result += sum_arr(m2[i]);
    }

    return result;
}

int sum_arr3(int m3[4][10][100])
{
    int result = 0;
    for (int i = 0; i < 4; i++)
    {
        result += sum_arr2(m3[i]);
    }

    return result;
}

int sum(s struct_to_sum)
{

    int result = 0;
    result += sum_arr3(struct_to_sum.m3);

    return result;
}