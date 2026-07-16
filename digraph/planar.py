import json
from random import random

import networkx as nx
import matplotlib.pyplot as plt
from networkx.drawing.nx_pydot import graphviz_layout


def draw(n : dict):
    g = nx.PlanarEmbedding()
    g.set_data(n)
    pos = nx.planar_layout(g)  # here are your positions.
    # pos = nx.spring_layout(g, pos=pos, seed=int(2**32 - 1 * random()))
    nx.draw_networkx(g, pos, with_labels=True)
    plt.show()

if __name__ == '__main__':
    j_obj = {}
    with open('planar.json', 'r') as infile:
        nodes = json.load(infile)
        infile.close()
    draw(nodes)
