###### or-tools

### Examples and Models

#### Seating - A Delegate Seating Problem
_This is the problem that introduced me to **or-tools**._

There is a one day event that covers several named sessions.
The seating for the event does not change: seats are arranged in named rows of different lengths. 

Company (organisation) delegates should always sit together, and a delegate should not have to switch seats if attending successive sessions.

What makes this more complex than e.g. a wedding planner is that delegates do not go to all sessions.

So, the constraints are:
* Seating is in rows. Each row has an arbitrary number of seats. 
* Each named delegate belongs to one named organisation.
* Each delegate will attend at least one session.
* Delegates of each organisation sit in adjacent seats in a session.
* Each delegate will sit in the same place in consecutive sessions.
* Each seat can only sit one delegate per session.
* Each delegate is assigned a maximum of one chair in each session.


