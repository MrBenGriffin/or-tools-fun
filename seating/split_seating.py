# Copyright 2019 Ben Griffin; All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
  Delegate Seating Problem
      There is a one day event that covers several named sessions.
      The seating for the event does not change: seats are arranged in named rows of different lengths.
      Company (organisation) delegates should always sit together, and a delegate should not have to switch seats if
       attending successive sessions.
      So, the constraints are:
      - Each named delegate belongs to one named organisation.
      - Each delegate will attend at least one session.
      - Delegates of each organisation sit in adjacent seats in a session.
      - Each delegate will sit in the same place in consecutive sessions.
      - Each seat can only sit one delegate per session..
      - Each delegate is assigned a maximum of one chair in each session.

      To cut down on work, we segment the data into tranches and solve each of them independently.
      This is done in two separate solves - one for the rows, and the other for the organisations.
      Both of these are variations of bin-packing and also lend themselves well to constraint programming.

      (1) Rows: Identify the rows for each tranche and the number of tranches.
      We choose how many seats each tranche should work with (tranche_size).
      The number depends upon the number of sessions, and the size of rows. 60 is a good start.
      We also want to allow for some slack (such that we have wiggle room when
      allocating delegates) - so eg. 15, which would give us an optimum allocation of 60-15 = 45 in this case.
      The maximum number of seats will be the maximum (row_size, tranche_size).
      We want to maximise the number of optimally allocated tranches.
      So, the constraints are:
        - Maximum number of tranches will be the number of rows
        - Each row can be used up to 1 time in each tranche
        - The value of a tranche will be the number of seats that it has allocated to it.
        - The value of a tranche will be less than or equal to optimal while being as full as possible.
        - Otherwise the value of a tranche will be less than or equal to the tranche_size if possible.
        - Otherwise the value of a tranche must be less than the maximum number of seats allowed in a tranche.

      (2) Organisations: Identify the organisations in each tranche.
      Each organisation has a count of delegates for each session, so we can use this as a bin-pack with
      the additional component of dealing with variation of weights over session. We also want to have some
      slack if possible.

      So, the constraints are:
        - All organisations must be allocated, and must be sat just once if it has any delegates.
        - Each tranche has some wiggle room (enforced by a fixed value) to assist in allocation
        - Each organisation can only belong to one tranche
        - The value of an organisation (and therefore it's tranche fill) changes on each session.
        - A tranche value must be less than the count of delegates of each of it's allocated organisations
        - The value of a tranche will be less than or equal to optimal while being as full as possible.

  Data Representation
      This uses a json file (for portability), which is a single dict containing the following:

      sessions is a list of session names.
      "sessions": ["08:00", "10:00", "12:00", ...]

      rows is a dict of row names with the number of contiguous seats it contains.
      split rows should be considered different - e.g. if row A is split by a walkway, call it A1 and A2
      "rows": { "A": 22, "B": 22, ...}

      orgs is a dict of organisations keyed by organisation name.
      "orgs" { "Amazon": {...}, "Google": {...}, ...}

      The dict within each organisation is it's set of delegates, again keyed by name...
      Against each delegate is that delegate's own request for session attendance.
      Eg. for Bjorn below, he wants to go to all sessions but the third.
      The sample data uses the first two characters of each organisation name for the person's name.
      Such that the organisation "BJ" is represented by Bjork and Bjorn
      "BJ":
        {
            "Bjork": [0, 1, 1, 1, 1],
            "Bjorn": [1, 1, 0, 1, 1]
        },

      The result is stored into a json file as a dict of sessions, which contains a dict of rows
      and the ordered list of delegate allocations, with a null for empty seats.
      "08:00": {
        "Ra": ["Mary", "Rana", ....],
        "Rb": [null,  "Liza",...],
        ...
      "10:00": {
        "Ra": [null,  "Rana", ....],
        "Rb": [null,  "Liza",...],

"""

import json
from random import choices
from ortools.sat.python import cp_model

# Adjust this to the number of cores you want to allocate.
workers = 4


def store_row_tranches(data, solver, basis):
    # This uses the result from solve_row_tranches
    # and generates a list of rows for each tranche, and a list of the number of chairs.
    # row_tranches:  [['I', 'J'], [], ['H', 'M'], ['K', 'L'], ['C', 'F'], ['E', 'N']]
    # seat_tranches: [48, 0, 48, 48, 44, 46]
    # Need to remove empty tranches (if there are any).
    row_names = [row for row in data['rows']]
    data['row_tranches'] = []
    data['seat_tranches'] = []
    # below looks odd  - but len(row_names) is number of rows, which is maximum number of tranches..
    for t_idx in range(len(row_names)):
        t_row = []
        t_size = 0
        for r_idx, r_name in enumerate(row_names):
            if solver.Value(basis[r_idx, t_idx]) > 0:
                t_row.append(r_name)
                t_size += data['rows'][r_name]
        if t_size != 0:
            data['row_tranches'].append(t_row)
            data['seat_tranches'].append(t_size)
    data['tranche_count'] = len(data['seat_tranches'])
    # don't really need to store this, but it helps keep track of what is going on..
    # with open('row_tranches_result.json', 'w') as outfile:
    #     json.dump([data['row_tranches'], data['seat_tranches']], outfile, sort_keys=True)


def solve_row_tranches(data, tranche_seats: int, row_slack: int):
    print("solving row tranches...")
    # Take a dict of "rows" and their seat count: { "A": 22, ... }
    # Use the rows to fill row tranches of size indicated by tranche_seats.
    # Although each tranche should allocate < tranche_seats this may be a problem if rows are larger than
    # tranche_seats. It's also important that we use all rows available.
    # calculate the number of adjusted rows by giving each adj.row tranche_seats seats.
    model = cp_model.CpModel()
    basis = {}

    optimum_seats = tranche_seats - row_slack
    all_rows_list = [data['rows'][row] for r_idx, row in enumerate(data['rows'])]
    row_num = len(all_rows_list)
    # start off with as many tranches as there are rows..
    t_range = range(row_num)
    r_range = range(row_num)

    max_row_seats = max(all_rows_list)
    maximum_seats = max(max_row_seats, tranche_seats + 1)

    for t_idx in t_range:
        for r_idx in r_range:
            basis[r_idx, t_idx] = model.NewBoolVar(f'{r_idx}.{t_idx}')

    for r_idx in range(len(all_rows_list)):
        model.Add(sum(basis[r_idx, t_idx] for t_idx in t_range) <= 1)

    slacks = [model.NewBoolVar(f's{t_idx}') for t_idx in t_range]
    oflows = [model.NewBoolVar(f'o{t_idx}') for t_idx in t_range]

    value = []
    for t_idx in t_range:
        value.append(model.NewIntVar(0, maximum_seats, f'v{t_idx}'))
        model.Add(value[t_idx] == sum([basis[r_idx, t_idx] * all_rows_list[r_idx] for r_idx in r_range]))
        model.Add(value[t_idx] <= optimum_seats).OnlyEnforceIf(slacks[t_idx])
        model.Add(value[t_idx] > optimum_seats).OnlyEnforceIf(slacks[t_idx].Not())
        model.Add(value[t_idx] <= tranche_seats).OnlyEnforceIf(oflows[t_idx])
        model.Add(value[t_idx] > tranche_seats).OnlyEnforceIf(oflows[t_idx].Not())
        model.Add(value[t_idx] <= maximum_seats)

    # Maximize total value of packed items.
    model.Maximize(sum(value))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        store_row_tranches(data, solver, basis)
    else:
        print("solve_row_tranches failed.\n", solver.ResponseStats())
        exit(0)


def store_tranche_orgs(data, solver, basis):
    # tranche_orgs [['AA', 'AB', 'SJ'],['EA'], ..] with the same number of elements as row_tranche.
    t_range = range(len(data['seat_tranches']))
    s_range = range(len(data['sessions']))
    o_range = range(len(data['org_sess_sum']))
    org_names = list(data['orgs'].keys())
    data['tranche_orgs'] = []
    data['tranche_org_seats'] = []
    for t_idx in t_range:
        data['tranche_orgs'].append([])
        data['tranche_org_seats'].append([])
        for s_idx in s_range:
            data['tranche_org_seats'][t_idx].append(0)
            for o_idx in o_range:
                if solver.Value(basis[t_idx, o_idx]) > 0:
                    org = org_names[o_idx]
                    data['tranche_org_seats'][t_idx][s_idx] += data['org_sess_sum'][org][s_idx]
                    if org not in data['tranche_orgs'][t_idx]:
                        data['tranche_orgs'][t_idx].append(org)
    # with open('tranche_orgs_result.json', 'w') as outfile:
    #     json.dump([data['tranche_orgs'], data['tranche_org_seats']], outfile, sort_keys=True)


def solve_tranche_orgs(data, row_slack: int, row_force: int):
    print("solving organisation tranches...")
    # We need to allocate groups of organisations that can fit into the seat_tranches bins.
    # Our product should be a list of tranche-orgs.. eg..
    # tranche_orgs: [['AA', 'AB', 'SJ'],['EA'], ..] with the same number of elements as row_tranche.
    # So this is looks like a multi-bin pack with a time-variant twist
    # and slack to allow for seating to find feasible.

    # t_range: range over 'bins (tranches)' of different capacities.
    t_range = range(len(data['seat_tranches']))  # [48, 44, 48, 48, 44, 46]

    # o_range: range over organisations/objects, with their volume-per-session
    o_range = range(len(data['org_sess_sum']))  # {'AD': [3, 2, 1, 3, 3], 'AE': [1, 3, 4, 1, 2], ... }

    # s_range range over time points (sessions) (org-volume changes at each point).
    # this could also be derived by len(data['org_sess_sum'][0])
    s_range = range(len(data['sessions']))      # ['08:00', '10:00', '12:00', '14:00', '16:00']

    model = cp_model.CpModel()

    # set up basis: the variations of possibility.
    # each org can be in a given tranche (across all sessions)
    basis = {}
    for t_idx in t_range:
        for o_idx in o_range:
            basis[t_idx, o_idx] = model.NewBoolVar(f'o{t_idx}.{o_idx}')

    for t_idx in t_range:  # In this tranche..
        for s_idx in s_range:  # In each session
            model.Add(  # ... ensure that...
                row_force + sum(  # there are always row_forced seats for allocation...
                    basis[t_idx, o_idx] * data['org_sess_sum'][org][s_idx] for o_idx, org in
                    enumerate(data['org_sess_sum'])  # ... all the organisation chair allocations is ...
                ) <= (data['seat_tranches'][t_idx])  # <= the seats made available to this tranche.
            )

    # each organisation must be sat just once.
    for o_idx, org in enumerate(data['org_sess_sum']):  # for each organisation...
        if sum(data['org_sess_sum'][org]) > 0:
            model.Add(sum([basis[t_idx, o_idx] for t_idx in t_range]) == 1)
        else:
            model.Add(sum([basis[t_idx, o_idx] for t_idx in t_range]) == 0)

    s_values = [model.NewIntVar(0, data['sess_sum'][s_idx], f's{s_idx}') for s_idx in s_range]
    for s_idx in s_range:
        model.Add(s_values[s_idx] == sum(
            basis[t_idx, o_idx] * data['org_sess_sum'][org][s_idx]
            for o_idx, org in enumerate(data['org_sess_sum'])
            for t_idx in t_range
        ))

    slacks = [model.NewBoolVar('w_%i' % t_idx) for t_idx in t_range]
    t_values = [model.NewIntVar(0, data['seat_tranches'][t_idx], f't{t_idx}') for t_idx in t_range]
    for t_idx in t_range:
        model.Add(t_values[t_idx] == sum(basis[t_idx, o_idx] for o_idx in o_range))
        optimum_seats = data['seat_tranches'][t_idx] - row_slack
        model.Add(t_values[t_idx] <= optimum_seats).OnlyEnforceIf(slacks[t_idx])
        model.Add(t_values[t_idx] > optimum_seats).OnlyEnforceIf(slacks[t_idx].Not())

    model.Maximize(sum(s_values))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        store_tranche_orgs(data, solver, basis)
    else:
        print("solve_tranche_orgs failed.\n", solver.ResponseStats())
        exit(0)


def create_data_model(data_model_file: str, seats_per_tranche: int = 60, row_slack: int = 10, row_force: int = 5):
    print("creating data model...")
    if data_model_file:
        with open(data_model_file, 'r') as infile:
            data = json.load(infile)
            sessions = len(data['sessions'])
            solve_row_tranches(data, seats_per_tranche, row_slack)

    else:
        # Use this for test data!
        # Load sessions and rows. a json file with the structure..
        # { "sessions": ["08:00", "10:00", "12:00", ...], "rows": { "A": 22, "B": 22, ...} }
        # -- Where sessions is a list of session names and rows is a dict of row_name->number_of_chairs.
        with open('sess_rows.json', 'r') as infile:
            data = json.load(infile)
        sessions = len(data['sessions'])
        solve_row_tranches(data, seats_per_tranche, row_slack)

        # Load organisation and delegates, (optionally with session requests). json file with the structure..
        # { "Org1": { "Del1":  [1, ...],  "Del2":  [0, ...] ... }, "Org2: { "Del1": .... }, ... }
        # -- Where orgs is a dict of delegates, each holding a list of session requests mapping onto the sessions.
        with open('orgs.json', 'r') as infile:
            orgs = json.load(infile)
        # We are going to ez-encode the names just to make it easier to evaluate test scenarios..
        # Orgs will be named AA,AB,AC... ZZ,
        # Delegate names will include the Org. name and a delegate number eg AA001, AA002, etc.
        data['orgs'] = {}
        for o_idx, org in enumerate(orgs):
            org_n = chr(65 + o_idx // 26) + chr(65 + o_idx % 26)
            data['orgs'][org_n] = {}
            for d_idx, delegate in enumerate(orgs[org]):
                del_n = org_n + str(d_idx).zfill(3)
                data['orgs'][org_n][del_n] = orgs[org][delegate]
                # Now populate delegate sessions if they are not set.
                if not orgs[org][delegate]:
                    session_request = [0]
                    while sum(session_request) == 0:
                        session_request = choices([0, 1], k=sessions)
                    data['orgs'][org_n][del_n] = session_request
        # Now save the new model
        with open('data_model.json', 'w') as outfile:
            json.dump(data, outfile, sort_keys=True)

    data['seats_sum'] = sum(data['seat_tranches'])
    data['org_sess_sum'] = {
        org: [
            sum([person[session] for person in data['orgs'][org].values()]) for session in range(sessions)
        ] for o_idx, org in enumerate(data['orgs'])}
    data['sess_sum'] = [
        sum([data['org_sess_sum'][o_idx][s_idx] for o_idx in data['org_sess_sum']]) for s_idx in range(sessions)
    ]
    if max(data['sess_sum']) > data['seats_sum']:
        print("Not enough seats (", str(data['seats_sum']), ") for the session requests (", max(data['sess_sum']), ")")
        exit(0)
    solve_tranche_orgs(data, row_slack, row_force)
    data['results'] = {session: {row: [] for row in data['rows']} for session in data['sessions']}
    return data


def store_allocation(data, or_vars, tranche):
    data['result'] = {}
    for s_idx, s_name in enumerate(data['sessions']):
        data['result'][s_name] = {}
        for r_idx, row in enumerate(data['rows']):
            data['result'][s_name][row] = []
            for c_idx in range(data['rows'][row]):
                chair = None
                for o_idx, o_name in enumerate(data['orgs'].keys()):
                    for d_idx, d_name in enumerate(data['orgs'][o_name].keys()):
                        if data['orgs'][o_name][d_name][s_idx] == 1 and \
                                tranche.Value(or_vars[(d_idx, o_idx, s_idx, r_idx, c_idx)]) > 0:
                            chair = d_name
                data['result'][s_name][row].append(chair)


def allocate(data, tranche_idx):
    print(f"calculating seating allocation #{tranche_idx}...")
    model = cp_model.CpModel()
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.max_time_in_seconds = 60

    del_chairs = {}
    org_chairs = {}

    # bool var for each legal seat for each delegate and for each organisation..
    for o_idx, o_name in enumerate(data['orgs']):
        del_sessions = data['orgs'][o_name]
        for d_idx, del_n in enumerate(del_sessions):
            for s_idx, s_name in enumerate(data['sessions']):
                if del_sessions[del_n][s_idx] == 1:
                    one_chair_constraint = []
                    for r_idx, r_name in enumerate(data['rows']):
                        for c_idx in range(data['rows'][r_name]):
                            o_tuple = o_idx, s_idx, r_idx, c_idx
                            d_tuple = d_idx, o_idx, s_idx, r_idx, c_idx
                            d_early = d_idx, o_idx, s_idx - 1, r_idx, c_idx
                            if o_tuple not in org_chairs:
                                org_chairs[o_tuple] = model.NewBoolVar(f'{o_idx}.{s_idx}.{r_idx}.{c_idx}')
                            del_chairs[d_tuple] = model.NewBoolVar(f'{d_idx}.{o_idx}.{s_idx}.{r_idx}.{c_idx}')
                            # Every delegate belongs to their organisation
                            model.AddImplication(del_chairs[d_tuple], org_chairs[o_tuple])
                            # Each delegate is assigned to exactly one chair in each session.
                            one_chair_constraint.append(del_chairs[d_tuple])
                            # If the delegate sat in the previous session, they must sit in the same place they sat
                            if d_early in del_chairs:
                                model.Add(del_chairs[d_tuple] == del_chairs[d_early])
                    if len(one_chair_constraint) > 0:
                        model.Add(sum(one_chair_constraint) == 1)
    # sum(sum(j for j in i) for i in a)
    # each organisation must be sat and requires adjacent seats.
    for o_idx, o_name in enumerate(data['orgs']):
        for s_idx, s_name in enumerate(data['sessions']):
            # All seats must be filled by organisation.
            chair_list = []
            for r_idx, r_name in enumerate(data['rows']):
                for c_idx in range(data['rows'][r_name]):
                    o_tuple = o_idx, s_idx, r_idx, c_idx
                    if o_tuple in org_chairs:
                        chair_list.append(org_chairs[o_tuple])
            if chair_list:
                model.Add(sum(chair_list) == data['org_sess_sum'][o_idx][s_idx])

            # Organisations must be sat together.
            adjacency_constraint = []
            for r_idx, r_name in enumerate(data['rows']):
                for c_idx in range(data['rows'][r_name] - data['org_sess_sum'][o_idx][s_idx] + 1):
                    tmp = model.NewBoolVar('')
                    adjacency_constraint.append(tmp)
                    model.AddBoolAnd(
                        org_chairs[o_idx, s_idx, r_idx, c_idx + i]
                        for i in range(data['org_sess_sum'][o_idx][s_idx])
                    ).OnlyEnforceIf(tmp)
            model.AddBoolOr(adjacency_constraint)

    # Each chair can only sit up to one delegate per session..
    for s_idx, s_name in enumerate(data['sessions']):
        for r_idx, r_name in enumerate(data['rows']):
            for c_idx in range(data['rows'][r_name]):
                chair_list = []
                for dc in del_chairs.keys():
                    if dc[2] == s_idx and dc[3] == r_idx and dc[4] == c_idx:
                        chair_list.append(del_chairs[dc])
                if chair_list:
                    model.Add(sum(chair_list) <= 1)

    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        store_allocation(data, del_chairs, solver)
    else:
        print(f'allocate {tranche_idx} failed\n', solver.ResponseStats())


def store_tranche(data, tranche_data):
    if 'result' in tranche_data:
        for session in data['sessions']:
            for row, allocation in tranche_data['result'][session].items():
                data['results'][session][row] = allocation


def print_solution(data):
    for session_name, session in sorted(data['results'].items()):
        rows_str = ""
        for row, chairs in sorted(session.items()):
            row_str = row + ":"
            p_chair = "**"
            for chair in chairs:
                row_str = row_str + (' ' if chair and chair[:2] == p_chair else '|') + (chair if chair else '_____')
                p_chair = "**" if not chair else chair[:2]
            rows_str = rows_str + row_str + "| "
        print(session_name + ':', rows_str)
    with open('result.json', 'w') as outfile:
        json.dump(data['results'], outfile, sort_keys=True)


def main():
    # 60: This splits the number of seats to process at about 60 a time, which seems to be solved quite rapidly.
    #     The larger the number, the slower - but more complete - the seating solver will be.
    # 15: This is how much slack to give each row allocation. We want to spread rows out a bit.
    #     It's also used to spread delegates out amongst each tranche.
    # 5:  This is a forced amount of seats left free in each tranche to ensure that the seating algorithm has enough
    #     flexibility to fit delegates.
    data = create_data_model("data_model.json", 60, 15, 5)
    tranches = data['tranche_count']
    print(f"solving seating for {tranches} tranches.")
    for tranche_idx in range(tranches):
        tranche_data = {
            'sessions': data['sessions'],
            'rows': {row: data['rows'][row] for row in data['rows'] if row in data['row_tranches'][tranche_idx]},
            'orgs': {org: data['orgs'][org] for org in data['orgs'] if org in data['tranche_orgs'][tranche_idx]},
            'org_sess_sum':
                [data['org_sess_sum'][org] for org in data['orgs'] if org in data['tranche_orgs'][tranche_idx]],
         }
        tranche_data['sess_sum'] = [
            sum(org[s_id] for org in tranche_data['org_sess_sum']) for s_id in range(len(data['sessions']))
        ]
        # with open('data_model_' + str(tranche_idx) + '.json', 'w') as outfile:
        #     json.dump(tranche_data, outfile, sort_keys=True)

        # Now allocate seats!
        allocate(tranche_data, tranche_idx)
        store_tranche(data, tranche_data)
    print_solution(data)


if __name__ == '__main__':
    main()
