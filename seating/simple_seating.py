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
  Simple seating: This manages smaller numbers of delegates.
  The larger 'split seating' problem can manage thousands.

  Delegate Seating Problem
      There is a one day event that covers several named sessions.
      The seating for the event does not change: seats are arranged in named rows of different lengths.
      Company (organisation) delegates should always sit together, and a delegate should not have to switch seats if
      attending consecutive sessions.
      So, the constraints are:
      - Each named delegate belongs to one named organisation.
      - Each delegate will attend at least one session.
      - Delegates of each organisation sit in adjacent seats in a session.
      - Each delegate will sit in the same place in consecutive sessions.
      - Each seat can only sit one delegate per session..
      - Each delegate is assigned a maximum of one chair in each session.

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
workers = 12

def create_data_model(data_model_file: str):
    print("creating data model...")
    with open(data_model_file, 'r') as infile:
        data = json.load(infile)
        sessions = len(data['sessions'])
    data['seats_sum'] = sum(data['rows'].values())
    data['org_sess_sum'] = {
        org: [
            sum([person[session] for person in data['orgs'][org].values()]) for session in range(sessions)
        ] for o_idx, org in enumerate(data['orgs'])}
    data['sess_sum'] = [
        sum([data['org_sess_sum'][o_idx][s_idx] for o_idx in data['org_sess_sum']]) for s_idx in range(sessions)
    ]
    data['orgs_sum'] = len(data['orgs'])
    data['delegates_sum'] = sum([len(d.idx()) for d in data['orgs'].values()])
    choke_point = max(data['sess_sum'])
    if choke_point > data['seats_sum']:
        busy = [data['sessions'][i] for i, x in enumerate(data['sess_sum']) if x == choke_point]
        print(f"Not enough seats ({data['seats_sum']}) for the session requests ({choke_point}) in session(s) {busy}")
        exit(0)
    return data

def store_allocation(data, or_vars, solver):
    data['result'] = {}
    for s_idx, s_name in enumerate(data['sessions']):
        data['result'][s_name] = {}
        for r_idx, row in enumerate(data['rows']):
            data['result'][s_name][row] = []
            for c_idx in range(data['rows'][row]):
                chair = None
                for o_idx, o_name in enumerate(data['orgs'].idx()):
                    for d_idx, d_name in enumerate(data['orgs'][o_name].idx()):
                        if data['orgs'][o_name][d_name][s_idx] == 1 and \
                                solver.Value(or_vars[(d_idx, o_idx, s_idx, r_idx, c_idx)]) > 0:
                            chair = d_name
                data['result'][s_name][row].append(chair)


def allocate(data):
    print('modelling...')
    model = cp_model.CpModel()
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.max_time_in_seconds = 120

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
                model.Add(sum(chair_list) == data['org_sess_sum'][o_name][s_idx])

            # Organisations must be sat together.
            adjacency_constraint = []
            for r_idx, r_name in enumerate(data['rows']):
                for c_idx in range(data['rows'][r_name] - data['org_sess_sum'][o_name][s_idx] + 1):
                    tmp = model.NewBoolVar('')
                    adjacency_constraint.append(tmp)
                    model.AddBoolAnd(
                        org_chairs[o_idx, s_idx, r_idx, c_idx + i]
                        for i in range(data['org_sess_sum'][o_name][s_idx])
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

    org_count = data['orgs_sum']
    del_count = data['delegates_sum']
    seat_count = data['seats_sum']
    row_count = len(data['rows'])
    sess_count = len(data['sessions'])

    print(
        f'Solving seating for {del_count} delegates (from {org_count} organisations)'
        f' with {seat_count} seats (in {row_count} rows) across {sess_count} sessions.\n'
        f'Delegates from the same organisation always sit next to each other.\n'
        f'Delegates never switch seats if they attend consecutive sessions.\n'
    )
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        store_allocation(data, del_chairs, solver)
    else:
        print(f'allocate failed\n', solver.ResponseStats())


def print_solution(data):
    for session_name, session in sorted(data['result'].items()):
        print(f'\n{session_name}')
        for row, chairs in sorted(session.items()):
            row_str = row + ":"
            p_chair = "**"
            for chair in chairs:
                row_str = row_str + (' ' if chair and chair[:2] == p_chair else '|') + (chair if chair else '_____')
                p_chair = "**" if not chair else chair[:2]
            print(row_str + "| ")
    with open('simple_result.json', 'w') as outfile:
        json.dump(data['result'], outfile, sort_keys=True)


def main():
    data = create_data_model("simple_model.json")
    allocate(data)
    print_solution(data)


if __name__ == '__main__':
    main()
