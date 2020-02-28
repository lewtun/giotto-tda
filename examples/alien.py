from PyGEL3D import gel
from PyGEL3D import js

def main():

    m = gel.obj_load("alien.obj")

    pos = m.positions()


    viewer = gel.GLManifoldViewer()
    viewer.display(m, mode='g', data=pos[:,2], bg_col=[1,1,1])

if __name__ == "__main__":
    main()