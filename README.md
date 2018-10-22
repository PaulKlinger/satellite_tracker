[![](http://img.youtube.com/vi/Xof4bjcwHAY/0.jpg)](http://www.youtube.com/watch?v=Xof4bjcwHAY "Project video")

This is the code and hardware design for my [Satellite tracker](https://www.reddit.com/r/space/comments/9py5qd/i_made_a_thingy_that_shows_satellites_and_space/).
It's in an extremely rough state...

The orbit_np.py file is a modified version of [pyorbital](https://github.com/pytroll/pyorbital)
(it calculates the orbits of multiple satellites at the same to increase performance).

Requires https://github.com/PaulKlinger/LIBtft144 and https://github.com/jgarff/rpi_ws281x + a bunch of libraries from PyPi.

The PCB design for the LED boards is in the PCBs folder. Note that it has a horrible design flaw:
Because of the positioning of the connections on each side the cables in the pillars have to cross over on each level,
making the assembly extremely frustrating.

The STLs and Fusion 360 source for the 3d printed parts are in the "3D printed parts" folder.
I'd strongly recommend that anyone who builds this uses threaded rods through the pillars instead of the million screws
I used. (I just didn't have any rods and wanted to build it right away.)
