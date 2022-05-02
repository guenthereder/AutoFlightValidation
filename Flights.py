#!/usr/bin/env python3

f4f_points_dict = {
    'A': 1.3,
    'B': 1.2,
    'C': 1.1,
    'D': 1.0,
    'CCC': 0.9
}

class Flight:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __str__(self):
        return self.pilot_name + ", " + self.launch_site \
               + ", " + str(self.points) + ", " + self.glider

    def get_flyforfun_points(self):
        if self.glider in f4f_points_dict:
            return self.points * f4f_points_dict[self.glider]
        else:
            print("Glider not in dict, CCC rating 0.9")
            return self.points * 0.9

