## or-tools: Examples and Models

* [A Delegate Seating Problem](#seating---a-delegate-seating-problem)
* [Chessboard Problem Solver](#chessboard---legal-pieces-puzzle)
* [Polyomino Puzzle Solver](#polyomino-puzzle-solver)
* [Polycube Puzzle Solver](#polycube-puzzle-solver)
* [Digraph Solver](#digraph-solver)
* [Maze Solver](#maze-solver)

### Seating - A Delegate Seating Problem
_This is the problem that introduced me to **or-tools**._

**This was a real world problem - and the solver saved the organisers a fortune in seats.
It felt like real magic.**

The actual event involved seating nearly a thousand delegates. 
Finding a solution allowed for the organiser to choose the most suitable venue.

There is a one-day event that covers several named sessions.
The seating for the event does not change: seats are arranged in named rows of different lengths. 

Company (organisation) delegates should always sit together, and a delegate should not have to switch seats if attending consecutive sessions.

What makes this more complex than e.g. a wedding planner is that delegates do not go to all sessions.

So, the constraints are:
* Seating is in rows. Each row has an arbitrary number of seats. 
* Each named delegate belongs to one named organisation.
* Each delegate will attend at least one session.
* Delegates of each organisation sit in adjacent seats in a session.
* Each delegate will sit in the same place in consecutive sessions.
* Each seat can only sit one delegate per session.
* Each delegate is assigned a maximum of one chair in each session.

There are two files here - 
* 'simple_seating' is much easier to read, and deals with a hundred or so delegates.
* 'split_seating' should be able to manage thousands of delegates.

For example (this is the simple_seating model):
There are six sessions in the day - named by the time that the session takes place.
Sessions: ["08:00", "10:00", "12:00", "14:00", "16:00"]

There are 38 seats across 5 rows. Because there's a gap in one row we treat it as two rows.
Rows are labeled Ra ... Rf.

    Ra:|_____|_____|_____|_____|_____|_____|_____|_____| 
    Rb:|_____|_____|_____|        Rc:|_____|_____|_____| 
    Rd:|_____|_____|_____|_____|_____|_____|_____|_____| 
    Re:|_____|_____|_____|_____|_____|_____|_____|_____| 
    Rf:|_____|_____|_____|_____|_____|_____|_____|_____| 

There are 17 organisations, named with a letter: B,D,E,F,G,H,I,J,L,O,P,Q,R,S,T,W,Z
There are 49 delegates, and coincidentally the delegates' names start with the same letter as the organisation they represent.
For instance, the delegates from 'W' are named Waldo, Wally, Wanda, and Wayne.

**You may have noticed that there are more delegates than seats - that's because few delegates attend every session.**

Each delegate has selected which sessions she/he have decided to attend.
We store their decision against their name in the organisation.
So, in the schedule for 'W', we see Waldo will attend the 8:00, 10:00, and 14:00 sessions.

        "W":
        {
            "Waldo": [1, 1, 0, 1, 0],
            "Wally": [0, 0, 1, 1, 1],
            "Wanda": [1, 0, 1, 1, 1],
            "Wayne": [0, 1, 1, 1, 1]
        },

The full data for this example is in the 'simple_model.json'
Here is one possible result. Note that while the 08:00 and the 16:00 
sessions are filled, many of the delegates are different, but
no delegate moves seats when attending consecutive sessions. 

    08:00
    Ra:|Ogion Ogden|Billy Bilal|Inger India|Lynda Lynne| 
    Rb:|Enola Enoch|Jiles|        Rc:|Zelma Zenta Zetta| 
    Rd:|Gusta Gunny|Quinn Quint Queen|Soren Sofia Sofka| 
    Re:|Twink Twyla Twila|Rheta Rhoda Rhona|Homer Holly| 
    Rf:|Polly Posie|Dwane Dwain|Waldo Wanda|Wiley Wilma| 
    
    10:00
    Ra:|Ogion|_____|_____|Bilal|_____|_____|Lydia Lynne| 
    Rb:|Enola|Jimmy Jiles|        Rc:|_____|Zenta Zetta| 
    Rd:|Gusta|Inell|Quinn|Sonja Sonya Soren Solon Sofka| 
    Re:|_____|_____|Twila|Rheta Rhoda|_____|Homer Hosea| 
    Rf:|Polly Posie|Dwane Dwain|Waldo Wayne|Wilda Wilma| 
    
    12:00
    Ra:|Ogion Ogden|_____|Bilal Billy|_____|Lydia Lynda| 
    Rb:|Enola Ennis|Wiley|        Rc:|Zelma Zenta Zetta| 
    Rd:|Quint Queen Quinn|_____|Sofia Soren Solon Sofka| 
    Re:|_____|Twink Twila|Rhona Rhoda|Gunny|Homer Holly| 
    Rf:|Polly Posie|Dwane|Wally Wanda Wayne|Inger India| 
    
    14:00
    Ra:|Enoch|Ogden|Jimmy|Bilal Billy|Lynne Lydia Lynda| 
    Rb:|_____|Wilda Wiley|        Rc:|Zelma Zenta|_____| 
    Rd:|Quint|_____|_____|_____|Sonya Soren Solon Sofka| 
    Re:|Inell|Twink Twila|Rhona|Gusta Gunny|Hosea Holly| 
    Rf:|Polly Posie|Waldo Wally Wanda Wayne|_____|Dwain| 
    
    16:00
    Ra:|Ogion Ogden|Jimmy Jiles|Billy|Lynne Lydia Lynda| 
    Rb:|Wilma Wilda Wiley|        Rc:|Zelma Zetta|Twyla| 
    Rd:|Quint Quinn Queen|Sonja Sonya Sofia Solon Sofka| 
    Re:|Inell India|Rhoda Rhona|Gusta Gunny|Hosea Holly| 
    Rf:|Polly|Enola Ennis|Wally Wanda Wayne|Dwane Dwain| 


### Chessboard - Legal pieces puzzle
Given a library of pieces and their moves, 
and given a requirement of which pieces to use, and how many,
determine a solution such that no piece can be taken by another.

This is an extension of the N-Queens puzzle
E.g. find a solution for 6 queens, 2 knights, and maximum (2) kings.


     ♞■□■□■□♚
     ■□■♛■□■□
     □■□■□■♛■
     ■□♛□■□■□
     □■□■□♛□■
     ■♛■□■□■□
     □■□■♛■□■
     ♚□■□■□■♞

### Polyomino Puzzle Solver
This solves filling a space with a set of defined polyominoes.

_A polyomino is a plane geometric figure formed by joining one or more equal squares edge to edge.
It is a polyform whose cells are squares. It may be regarded as a finite subset of the regular square tiling._

This example includes a pentomino class.

A standard pentomino puzzle is to tile a rectangular box with the pentominoes, i.e. cover it without overlap and
without gaps. Each of the 12 pentominoes has an area of 5 unit squares, so the box must have an area of 60 units.
Possible sizes that use just one of each pentomino are 6×10, 5×12, 4×15 and 3×20.
The 6×10 case, first solved in 1960, has exactly 2339 solutions.
The 5×12 box has 1010 solutions, the 4×15 box has 368 solutions, and the 3×20 box has just 2 solutions
The 8×8 rectangle with a 2×2 hole in the center has 65 solutions.

This program allows any grid (with arbitrary holes) and allows a variety of shapes to be used to fill it.
e.g. 10x12 grid, with 8 x 'U' pentominoes and 1 or more 'F'.
If successful, it returns a box drawing of the result, e.g. for a 3x20 grid with 1 of each pentomino:

    ╔═══╦═╦═════╦═══════╦═╦═════╦═══╦═╦═════╗
    ║ ╔═╝ ╚═╗   ║ ╔═══╦═╝ ╚═╗ ╔═╝ ╔═╣ ╚═══╗ ║
    ║ ╚═╗ ╔═╩═══╩═╩═╗ ╚═══╗ ║ ║ ╔═╝ ╚═══╗ ║ ║
    ╚═══╩═╩═════════╩═════╩═╩═╩═╩═══════╩═╩═╝

### Polycube Puzzle Solver
This solves filling a 3D space with a set of defined polycubes.
It is roughly the same as the polyomino solver, but extended to three dimensions.

A pentacube is a polycube composed of 5 cubes.
There are 29 distinct three-dimensional pentacubes (Bouwkamp 1981).
Of these, the 12 planar pentacubes (corresponding to solid pentominoes), are well known.
Among the non-planar pentacubes, there are five that have at least one plane of symmetry;
Each of them is its own mirror image. The remaining 12 pentacubes come in mirror image pairs.

This will generate obj/mtl 3D 'Wavefront' files of the solution.

![Exploded](polycube/exploded.jpg)

![Packed](polycube/packed.jpg)


### Digraph Solver
This uses just one single constraint! AddCircuit()

An or-tools example implementing/demonstrating the AddCircuit constraint
Find path from 'start' to 'stop' through a directed graph (digraph) of nodes and arcs in a given number of steps.
steps can be a specific number, 'min', or 'max'

The problem codes the digraph as a dict of nodes : a list of the arcs from that node.
For instance,

```Python
a: ['o', 'd', 'b', 'y']  # node 'a' has 4 outgoing arcs:  a->o, a->d, a->b, a->y
```

This example:
* Generates a random problem with 61 nodes, all but the 'stop' node having 4 outgoing arcs.
* Prints the problem digraph
* Solves the minimum and maximum paths.
* Solves (or fails) for seeking path-lengths from minimum to maximum steps long printing the result.

For instance, using 26 nodes it may produce something like the following:

````text
a: ['g', 't', 'n', 'w']
b: ['p', 'g', 'l', 'n']
c: ['i', 'z', 'o', 'k']
d: ['y', 'x', 'p', 'z']
e: ['u', 'f', 'h', 'j']
f: ['n', 'q', 'l', 'j']
g: ['r', 'q', 'u', 'b']
h: ['m', 'v', 's', 'w']
i: ['p', 'w', 'q', 'v']
j: ['g', 'f', 'e', 'q']
k: ['n', 'p', 's', 'c']
l: ['q', 'n', 'u', 't']
m: ['d', 'k', 'x', 'r']
n: ['u', 'l', 'q', 's']
o: ['z', 'y', 'm', 'h']
p: ['o', 'x', 'l', 'j']
q: ['k', 'g', 'm', 'c']
r: ['n', 'h', 'k', 'j']
s: ['p', 'm', 'k', 'h']
t: ['k', 'u', 'i', 'c']
u: ['b', 's', 'w', 'd']
v: ['o', 'b', 'd', 'p']
w: ['l', 'o', 'f', 'e']
x: ['r', 'j', 'w', 'e']
y: ['p', 'x', 'h', 'g']
z: []

a-w-o-z
a-g-q-c-z
a-w-l-t-c-z
a-g-b-l-q-c-z
a-g-b-p-o-m-d-z
a-w-o-y-p-l-u-d-z
a-g-b-p-j-e-h-m-d-z
a-g-b-p-j-e-h-m-k-c-z
a-g-b-p-j-e-h-m-k-c-o-z
a-t-u-d-y-g-b-l-n-s-k-c-z
a-w-l-t-c-o-y-p-x-r-n-u-d-z
a-t-u-s-h-v-p-l-n-q-c-i-w-o-z
a-w-l-t-u-s-p-o-y-x-r-n-q-m-d-z
a-g-r-h-v-p-l-t-u-b-n-q-c-i-w-o-z
a-g-r-k-n-q-c-i-w-o-h-v-p-l-t-u-d-z
a-g-r-j-e-h-v-p-l-t-u-b-n-q-c-i-w-o-z
a-g-r-j-e-h-v-p-l-t-u-s-k-n-q-c-i-w-o-z
a-t-k-c-i-w-f-q-m-d-x-j-g-u-b-l-n-s-p-o-z
a-n-s-m-x-r-j-e-f-q-k-c-i-w-l-t-u-d-y-p-o-z
a-w-f-q-m-d-x-j-e-u-b-g-r-k-n-l-t-c-i-v-p-o-z
a-w-l-t-i-v-b-n-s-k-c-o-y-p-x-r-j-e-f-q-g-u-d-z
a-g-u-d-y-p-j-e-f-q-m-x-r-n-s-h-w-l-t-k-c-i-v-o-z
a-w-l-t-u-b-g-q-k-c-i-v-o-y-p-x-r-j-e-f-n-s-h-m-d-z
````

### Maze Solver
This is actually just an extension of the digraph solver above, but looks more pretty!
Here we generate a random 2D maze, and then we attempt to solve it.

This competes well against a naive wall-crawling (always keep a wall to my right) automaton.

````
┏━━━┳━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┳━━━┳━┳━━━━━━━━━━━━━━━┳━┓
┃o  ┃ . ┃       ┃         ┃         ┃           ┃       ┃   ┃ ┃               ┃ ┃
┃.┏━┛.╻.╹ ┏━━━┓ ┗━┳━━━╸ ╻ ╹ ╻ ┏━━━┓ ┗━━━╸ ┏━╸ ╻ ┃ ╻ ╻ ┏━┫ ╻ ┃ ┃ ╺━┓ ╺━┳━┳━━━┓ ┃ ┃
┃ ┃ . ┃ . ┃   ┃   ┃     ┃   ┃ ┃ . ┃       ┃   ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃   ┃   ┃ ┃   ┃ ┃ ┃
┃.╹.┏━╋━╸.┃ ╻ ┣━╸ ┃ ┏━━━┻━┓ ┃ ┃.╻.┗━┳━━━┳━┻━┓ ┃ ┣━┛ ┃ ╹ ╹ ┃ ┃ ┗━╸ ┣━╸ ┃ ┗━┓ ╹ ┃ ┃
┃ . ┃ ┃ . ┃ ┃ ┃   ┃ ┃ . . ┃ ┃ ┃ ┃ . ┃ . ┃ . ┃ ┃ ┃   ┃     ┃ ┃     ┃   ┃   ┃   ┃ ┃
┃ ┏━┛ ┃.┏━┛ ┃ ┃ ╺━┛ ┃.┏━┓.┗━┻━┫.┃ ╻.╹.╻.┃.╻.┃ ┗━┫ ┏━┻━┳━━━┫ ┣━━━┓ ┃ ╺━┫ ╺━┫ ╺━┫ ┃
┃ ┃   ┃ ┃   ┃ ┃     ┃ ┃ ┃ .   ┃ ┃ ┃ . ┃ ┃ ┃ ┃   ┃ ┃   ┃   ┃ ┃   ┃ ┃   ┃   ┃   ┃ ┃
┃ ┃ ╻ ┃.┗━╸ ┃ ┣━━━┳━┛.┃ ┣━┓.╻ ┃.┗━┻━━━┫.╹.┃.┗━┓ ╹ ┃ ╻ ╹ ┏━┛ ┃ ┏━┻━╋━╸ ╹ ╻ ┗━┓ ┃ ┃
┃ ┃ ┃ ┃ .   ┃ ┃ . ┃ . ┃ ┃ ┃ ┃ ┃ . . . ┃ . ┃ . ┃   ┃ ┃   ┃   ┃ ┃ . ┃     ┃   ┃ ┃ ┃
┃ ┃ ┗━┻━┓.┏━┛ ┃.╻.╹.┏━┛ ┃ ╹.┃ ┃ ╺━┳━╸.┣━━━┻━┓.┗━━━┫ ┗━━━┛ ╻ ╹ ┃.╻.┃ ╺━┳━┻━┓ ┃ ╹ ┃
┃ ┃     ┃ ┃   ┃ ┃ . ┃   ┃ . ┃ ┃   ┃ . ┃     ┃ . . ┃       ┃   ┃ ┃ ┃   ┃   ┃ ┃   ┃
┃ ┗━┓ ╻ ┃.┣━━━┛.┣━━━┛ ╺━┫.╺━┻━┻━━━┛.┏━┛ ┏━╸ ┣━╸ ╻.┃ ╺━━━┳━┻━━━┛.┃.┣━╸ ┗━┓ ┃ ┗━┓ ┃
┃   ┃ ┃ ┃ ┃   . ┃       ┃ . . . . . ┃   ┃   ┃   ┃ ┃     ┃ . . . ┃ ┃     ┃ ┃   ┃ ┃
┃ ╻ ╹ ┃ ┃.┗━╸.╻ ╹ ┏━━━┓ ┗━━━━━━━┳━━━┫ ╺━┻━┓ ┃ ┏━┛.┣━━━┓ ┃.┏━━━┳━┛.┣━━━┓ ╹ ┣━╸ ┃ ┃
┃ ┃   ┃ ┃ . . ┃   ┃   ┃         ┃   ┃     ┃ ┃ ┃ . ┃ . ┃ ┃ ┃   ┃   ┃   ┃   ┃   ┃ ┃
┃ ┗━━━┻━┻━┓ ╺━┻━┳━┛ ╻ ┗━━━━━━━━━┛ ╻ ┗━┓ ╻ ┗━┛ ┃.╺━┫.╻.┣━┛.┃ ╻ ┗━┓.╹ ╻ ┣━╸ ┃ ╺━┫ ┃
┃         ┃     ┃   ┃             ┃   ┃ ┃     ┃ . ┃ ┃ ┃ . ┃ ┃   ┃   ┃ ┃   ┃   ┃ ┃
┣━━━━━┓ ┏━┻━━━┓ ┗━━━╋━╸ ┏━━━┳━━━━━┻━┓ ┗━┫ ┏━━━┻━┓.┃.┃.╹.╻ ┗━┛ ┏━┛.┏━┫ ┗━━━╋━┓ ┃ ┃
┃     ┃ ┃     ┃     ┃   ┃   ┃       ┃   ┃ ┃     ┃ ┃ ┃ . ┃     ┃ . ┃ ┃     ┃ ┃ ┃ ┃
┃ ╻ ┏━┛ ┣━━━┓ ┗━━━┓ ╹ ┏━┫ ╻ ┗━━━━━╸ ┣━╸ ┃ ╹ ┏━┓ ┃.╹.┣━━━┻━━━╸ ┃.╺━┫ ┣━━━┓ ┃ ┃ ┃ ┃
┃ ┃ ┃   ┃   ┃     ┃   ┃ ┃ ┃         ┃   ┃   ┃ ┃ ┃ . ┃         ┃ . ┃ ┃   ┃ ┃ ┃ ┃ ┃
┣━┛ ┃ ╺━┫ ╻ ┗━┳━╸ ┗━━━┛ ┃ ┗━┓ ┏━━━━━┛ ┏━┛ ┏━┛ ┃ ┗━━━╋━┓ ┏━━━━━┫ ╻.┃ ╹ ╻ ╹ ┃ ╹ ┃ ┃
┃   ┃   ┃ ┃   ┃         ┃   ┃ ┃       ┃   ┃   ┃     ┃ ┃ ┃     ┃ ┃ ┃   ┃   ┃   ┃ ┃
┃ ╺━┻━┓ ┃ ┗━┓ ╹ ╺━━━━━━━┛ ╻ ┃ ┗━━━┳━┳━┛ ┏━┛ ╻ ┣━┓ ╻ ╹ ┃ ┃ ┏━━━┻━┛.┃ ╺━╋━━━┛ ┏━┛ ┃
┃     ┃ ┃   ┃             ┃ ┃     ┃ ┃   ┃   ┃ ┃ ┃ ┃   ┃ ┃ ┃ . . . ┃   ┃     ┃   ┃
┃ ┏━╸ ┗━┻━┓ ┗━┳━━━━━┳━╸ ╺━┫ ┣━━━┓ ╹ ╹ ╻ ┣━╸ ┗━┫ ┗━┻━┳━┻━┛ ┃.╺━┳━━━┻━╸ ╹ ┏━━━┻━┓ ┃
┃ ┃       ┃   ┃     ┃     ┃ ┃   ┃     ┃ ┃     ┃     ┃     ┃ . ┃         ┃     ┃ ┃
┃ ┃ ╺━┳━━━┻━┓ ┃ ╺━┓ ┗━━━╸ ┃ ┗━┓ ┗━━━┳━┛ ┃ ╺━━━╋━━━┓ ┃ ┏━━━┻━╸.┗━┓ ╺━━━┳━┛ ╻ ╻ ┗━┫
┃ ┃   ┃     ┃ ┃   ┃       ┃   ┃     ┃   ┃     ┃   ┃ ┃ ┃       . ┃     ┃   ┃ ┃   ┃
┃ ┗━┓ ╹ ╻ ╻ ╹ ┣━━━┫ ┏━━━━━┻━╸ ┗━╸ ╻ ┃ ╻ ┗━┓ ╻ ┗━┓ ┃ ┃ ┣━━━━━━━┓.┣━━━━━╋━━━┫ ┣━┓ ┃
┃   ┃   ┃ ┃   ┃   ┃ ┃             ┃ ┃ ┃   ┃ ┃   ┃ ┃ ┃ ┃       ┃ ┃     ┃   ┃ ┃ ┃ ┃
┣━━━┻━┳━┻━╋━━━┛ ╻ ┃ ┣━━━╸ ╻ ┏━┳━━━┛ ┃ ┣━╸ ┃ ┗━┓ ┃ ┃ ┃ ╹ ╺━━━┓ ╹.┃ ┏━╸ ┗━┓ ╹ ╹ ┃ ┃
┃     ┃   ┃     ┃ ┃ ┃     ┃ ┃ ┃     ┃ ┃   ┃   ┃ ┃ ┃ ┃       ┃   ┃ ┃     ┃     ┃ ┃
┃ ╻ ╻ ╹ ┏━┛ ┏━┳━┛ ╹ ┃ ╺━┳━┻━┛ ┃ ┏━━━┛ ┃ ╺━╋━━━┛ ┃ ┃ ┗━━━┳━╸ ┣━╸.┃ ┗━━━┓ ┗━━━┓ ┃ ┃
┃ ┃ ┃   ┃   ┃ ┃     ┃   ┃     ┃ ┃     ┃   ┃     ┃ ┃     ┃   ┃ . ┃     ┃     ┃ ┃ ┃
┣━┛ ┣━╸ ┃ ╺━┫ ┗━┓ ╻ ┗━┓ ┃ ╺━┳━┛ ┃ ╺━┳━╋━╸ ╹ ┏━━━┛ ┗━┓ ╻ ┃ ╺━┫.╺━┻━━━╸ ┗━┳━╸ ┗━┫ ┃
┃   ┃   ┃   ┃   ┃ ┃   ┃ ┃   ┃   ┃   ┃ ┃     ┃       ┃ ┃ ┃   ┃ . . . . . ┃     ┃ ┃
┃ ╺━┻━━━┛ ┏━┻━┓ ┣━┻━╸ ┃ ┣━┓ ┣━━━┻━╸ ┃ ┃ ╺━━━┛ ╺━┳━╸ ┃ ┃ ┣━━━┻━━━━━━━━━┓.┗━┳━┓ ┃ ┃
┃         ┃   ┃ ┃     ┃ ┃ ┃ ┃       ┃ ┃         ┃   ┃ ┃ ┃             ┃ . ┃ ┃ ┃ ┃
┣━━━━━━━━━┛ ╻ ╹ ┃ ╺━┳━┫ ┃ ╹ ┃ ┏━━━┓ ╹ ┗━┳━━━┓ ╻ ┗━━━┛ ┃ ┃ ┏━╸ ┏━━━━━╸ ┗━┓.╹ ┃ ╹ ┃
┃           ┃   ┃   ┃ ┃ ┃   ┃ ┃   ┃     ┃   ┃ ┃       ┃ ┃ ┃   ┃         ┃   ┃   ┃
┃ ┏━━━┳━━━┓ ┗━┓ ┗━┓ ┃ ┗━┛ ╺━┛ ┃ ╻ ┗━━━┓ ┗━┓ ┃ ┗━━━┳━━━┫ ╹ ┃ ┏━┫ ┏━━━━━┳━┛.┏━┻━━━┫
┃ ┃   ┃   ┃   ┃   ┃ ┃         ┃ ┃     ┃   ┃ ┃     ┃   ┃   ┃ ┃ ┃ ┃     ┃ . ┃     ┃
┃ ┃ ╻ ┃ ╻ ┃ ╻ ┃ ┏━┛ ┣━━━━━┳━━━┫ ┃ ╺━━━┻━━━┛ ┗━┳━╸ ┃ ╻ ┗━┳━┫ ╹ ┃ ┗━┓ ╻ ┃.┏━┻━┓ ╻ ┃
┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃   ┃     ┃   ┃ ┃             ┃   ┃ ┃   ┃ ┃   ┃   ┃ ┃ ┃ ┃ . ┃ ┃ ┃
┃ ┃ ┣━┛ ┃ ┗━┫ ┣━┛ ┏━┫ ╻ ╺━┛ ╻ ┗━┫ ╻ ┏━━━━━━━┓ ╹ ┏━┛ ┗━┓ ┃ ┗━━━╋━╸ ┃ ┗━┫.┃.╻.┗━┫ ┃
┃ ┃ ┃   ┃   ┃ ┃   ┃ ┃ ┃     ┃   ┃ ┃ ┃       ┃   ┃     ┃ ┃     ┃   ┃   ┃ ┃ ┃ . ┃ ┃
┃ ╹ ┃ ╺━┻━┓ ╹ ┃ ┏━┛ ┃ ┣━━━━━┻━┓ ┣━┛ ┃ ╻ ╺━┳━┻━╸ ┃ ╺━┳━┛ ┃ ┏━┓ ┃ ╺━╋━╸ ┃.╹.┃ ╻.┃ ┃
┃   ┃     ┃   ┃ ┃   ┃ ┃       ┃ ┃   ┃ ┃   ┃     ┃   ┃   ┃ ┃ ┃ ┃   ┃   ┃ . ┃ ┃ ┃ ┃
┣━┓ ┣━╸ ╻ ┗━━━┻━┫ ╻ ╹ ┃ ╺━┳━━━┫ ┃ ┏━┛ ┣━╸ ┃ ┏━━━┻━┳━┛ ╺━┛ ┃ ┃ ┃ ╻ ╹ ╻ ┗━━━╋━┛.┃ ┃
┃ ┃ ┃   ┃       ┃ ┃   ┃   ┃   ┃ ┃ ┃   ┃   ┃ ┃     ┃       ┃ ┃ ┃ ┃   ┃     ┃   ┃ ┃
┃ ┗━┛ ┏━┻━┳━╸ ┏━┫ ┣━━━┻━╸ ╹ ┏━┛ ╹ ┣━━━┫ ╻ ┃ ╹ ┏━╸ ┃ ╺━┳━┳━┛ ╹ ┣━┫ ┏━┻━┓ ┏━┛ ╻.┃ ┃
┃     ┃   ┃   ┃ ┃ ┃         ┃     ┃   ┃ ┃ ┃   ┃   ┃   ┃ ┃     ┃ ┃ ┃   ┃ ┃   ┃ ┃ ┃
┣━━━━━┛ ╻ ┃ ╺━┛ ┃ ╹ ┏━━━━━┳━┻━━━━━┫ ╻ ╹ ┣━┻━━━┻━╸ ┣━╸ ┃ ╹ ┏━━━┫ ┃ ┃ ╻ ┗━┻━╸ ┃.┃ ┃
┃       ┃ ┃     ┃   ┃     ┃       ┃ ┃   ┃         ┃   ┃   ┃   ┃ ┃ ┃ ┃       ┃ ┃ ┃
┃ ╺━┳━━━┫ ┗━━━┓ ┗━━━┛ ┏━╸ ┃ ╺━┓ ╻ ╹ ┣━━━┛ ╻ ╺━┳━━━┛ ╺━┫ ┏━┛ ┏━┛ ┃ ┃ ┣━━━━━━━┫.┃ ┃
┃   ┃   ┃     ┃       ┃   ┃   ┃ ┃   ┃     ┃   ┃       ┃ ┃   ┃   ┃ ┃ ┃       ┃ ┃ ┃
┃ ╻ ╹ ╻ ┗━┓ ┏━┻━━━━━━━┫ ╺━┻━┓ ┃ ┃ ┏━┛ ╻ ╺━┻━┓ ┃ ┏━┳━╸ ┃ ┗━╸ ┃ ╺━┻━┛ ┃ ┏━━━┓ ┃.┃ ┃
┃ ┃   ┃   ┃ ┃         ┃     ┃ ┃ ┃ ┃   ┃     ┃ ┃ ┃ ┃   ┃     ┃       ┃ ┃   ┃ ┃ ┃ ┃
┃ ┣━┳━┻━╸ ┃ ┣━┓ ╺━━━┓ ┗━┓ ┏━┛ ┃ ┗━┛ ╻ ┃ ┏━╸ ┣━┛ ┃ ┃ ┏━┻━┓ ┏━┻━┳━━━━━┻━┛ ╻ ╹ ┃.┃ ┃
┃ ┃ ┃     ┃ ┃ ┃     ┃   ┃ ┃   ┃     ┃ ┃ ┃   ┃   ┃ ┃ ┃   ┃ ┃   ┃         ┃   ┃ ┃ ┃
┃ ┃ ┃ ╺━┳━┛ ┃ ┗━━━┓ ┗━━━┫ ╹ ┏━╋━━━━━╋━┻━┫ ┏━┛ ╻ ╹ ┃ ┃ ┏━┛ ┃ ╻ ┗━╸ ┏━━━━━┻━━━┫.╹ ┃
┃ ┃ ┃   ┃   ┃     ┃     ┃   ┃ ┃     ┃   ┃ ┃   ┃   ┃ ┃ ┃   ┃ ┃     ┃         ┃ . ┃
┃ ╹ ┣━╸ ┃ ┏━┛ ╺━┳━┻━━━╸ ┗━┳━┛ ┃ ┏━┓ ┃ ╻ ╹ ┃ ╺━╋━┓ ┃ ┃ ╹ ╺━┫ ┗━━━┳━┛ ┏━━━┳━╸ ┗━┓.┃
┃   ┃   ┃ ┃     ┃         ┃   ┃ ┃ ┃ ┃ ┃   ┃   ┃ ┃ ┃ ┃     ┃     ┃   ┃   ┃ . . ┃ ┃
┃ ┏━┛ ┏━┛ ┃ ╺━┓ ┃ ╺━┳━┳━╸ ╹ ╻ ┃ ╹ ┃ ╹ ┣━┓ ┗━┓ ┃ ┃ ┃ ┗━┳━╸ ┣━━━┓ ┃ ╺━╋━╸ ┃.┏━┓.┃.┃
┃ ┃   ┃   ┃   ┃ ┃   ┃ ┃     ┃ ┃   ┃   ┃ ┃   ┃ ┃ ┃ ┃   ┃   ┃   ┃ ┃   ┃   ┃ ┃ ┃ ┃ ┃
┃ ┃ ┏━┛ ╺━┻━━━┛ ┗━┓ ┃ ╹ ╺━┳━┻━╋━━━┻━━━┛ ┣━╸ ┃ ┃ ╹ ┗━━━┫ ╺━┻━╸ ┃ ┣━╸ ┃ ╻ ┃.┃ ┃.╹.┃
┃ ┃ ┃             ┃ ┃     ┃   ┃         ┃   ┃ ┃       ┃       ┃ ┃   ┃ ┃ ┃ ┃ ┃ . ┃
┃ ┃ ┣━━━━━━━━━━━━━┛ ┃ ┏━━━┛ ╻ ╹ ┏━╸ ┏━┓ ┃ ╺━┫ ┃ ┏━━━┓ ┃ ┏━━━━━┫ ╹ ╻ ┃ ┗━┫.╹ ┣━━━┫
┃ ┃ ┃               ┃ ┃     ┃   ┃   ┃ ┃ ┃   ┃ ┃ ┃   ┃ ┃ ┃     ┃   ┃ ┃   ┃   ┃ . ┃
┃ ┃ ╹ ┏━━━━━┳━╸ ┏━━━┻━┛ ┏━━━┫ ┏━┛ ┏━┛ ┃ ┣━┓ ╹ ┃ ╹ ┏━┛ ┃ ┃ ┏━┓ ┃ ┏━┻━┻━┓ ┃.╺━┛.╻.┃
┃ ┃   ┃     ┃   ┃       ┃   ┃ ┃   ┃   ┃ ┃ ┃   ┃   ┃   ┃ ┃ ┃ ┃ ┃ ┃     ┃ ┃ . . ┃ ┃
┃ ┗━━━┫ ╺━━━┫ ╺━┛ ┏━┳━━━┛ ┏━┛ ┃ ╺━┻━┓ ┃ ┃ ┗━┳━┻━┳━┛ ╺━┻━┛ ┃ ╹ ┃ ╹ ┏━┓ ╹ ┗━┳━━━┛.┃
┃     ┃     ┃     ┃ ┃     ┃   ┃     ┃ ┃ ┃   ┃   ┃         ┃   ┃   ┃ ┃     ┃   . ┃
┣━━━┓ ┃ ┏━┓ ┗━┳━━━┛ ┃ ╻ ╺━┫ ┏━┻━┳━╸ ┃ ╹ ╹ ┏━┛ ╻ ╹ ┏━┳━━━┓ ┃ ┏━┻━━━┫ ┗━━━╸ ┃ ╻.┏━┫
┃   ┃ ┃ ┃ ┃   ┃     ┃ ┃   ┃ ┃   ┃   ┃     ┃   ┃   ┃ ┃   ┃ ┃ ┃     ┃       ┃ ┃ ┃ ┃
┃ ╺━┻━┛ ╹ ┃ ╺━┛ ╺━┓ ╹ ┗━┓ ╹ ╹ ╻ ┃ ╺━┻━━━━━┛ ╺━┻━━━┛ ┃ ╺━┻━┛ ┃ ╻ ╺━┛ ╺━━━┳━┛ ┃.╹ ┃
┃         ┃       ┃     ┃     ┃ ┃                   ┃       ┃ ┃         ┃   ┃ .*┃
┗━━━━━━━━━┻━━━━━━━┻━━━━━┻━━━━━┻━┻━━━━━━━━━━━━━━━━━━━┻━━━━━━━┻━┻━━━━━━━━━┻━━━┻━━━┛
````

#### That's all for the moment!

