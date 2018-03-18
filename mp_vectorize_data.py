import numpy as np
import os
import re
import h5py
import socket
import struct
from multiprocessing import Process, Manager
from sklearn.preprocessing import normalize

LOG_REGEX = re.compile(r'([^\s]+)\s[^\s]+\s[^\s]+\s\[[^\]]+\]\s"([^\s]*)\s[^"]*"\s([0-9]+)')

def ip2int(addr):
    return struct.unpack("!I", socket.inet_aton(addr))[0]


def get_prevectors():
    data_path = "data/"
    workers = 8
    manager = Manager()
    prevectors = manager.dict()
    queue = manager.Queue(32)
    worker_pool = []
    for i in range(workers):
        p = Process(target=pre_parse, args=(queue, prevectors))
        print ("Starting worker ", str(i))
        p.start()
        worker_pool.append(p)
    
    for path in os.listdir(data_path):
        full_path = os.path.join(data_path, path)
        queue.put(full_path)

    for i in range(workers):
        queue.put(None)

    print ("Joining pools")
    for p in worker_pool:
       p.join()

    return prevectors


def pre_parse(queue,prevectors):
        my_prevectors = {}
        while True:
             full_path = queue.get()
             if full_path is None:
               prevectors.update(my_prevectors)
               break
             with open(full_path, "r") as f:
              for line in f:
                try: 
                   ip, request_type, response_code = LOG_REGEX.findall(line)[0]
                   ip = ip2int(ip)
                except IndexError:
                   continue

                if ip not in my_prevectors:
                    my_prevectors[ip] = {"requests": {}, "responses": {}}

                if request_type not in my_prevectors[ip]["requests"]:
                    my_prevectors[ip]['requests'][request_type] = 0

                my_prevectors[ip]['requests'][request_type] += 1

                if response_code not in my_prevectors[ip]["responses"]:
                    my_prevectors[ip]["responses"][response_code] = 0

                my_prevectors[ip]["responses"][response_code] += 1


def convert_prevectors_to_vectors(prevectors):
    request_types = [
        "GET",
        "POST",
        "HEAD",
        "OPTIONS",
        "PUT",
        "TRACE"
    ]
    response_codes = [
        200,
        404,
        403,
        304,
        301,
        206,
        418,
        416,
        403,
        405,
        503,
        500,
    ]

    vectors = np.zeros((len(prevectors.keys()), len(request_types) + len(response_codes)), dtype=np.float32)
    ips = []

    for index, (k, v) in enumerate(prevectors.items()):
        ips.append(k)
        for ri, r in enumerate(request_types):
            if r in v["requests"]:
                vectors[index, ri] = v["requests"][r]
        for ri, r in enumerate(response_codes):
            if r in v["responses"]:
                vectors[index, len(request_types) + ri] = v["requests"][r]

    return ips, vectors


if __name__ == "__main__":
    print ("Starting pre-vectorization")
    prevectors = get_prevectors()
    ips, vectors = convert_prevectors_to_vectors(prevectors)
    print ("Starting normalization")
    vectors = normalize(vectors)

    print ("Building samples")
    with h5py.File("secrepo_mp.h5", "w") as f:
        f.create_dataset("vectors", shape=vectors.shape, data=vectors)
        f.create_dataset("cluster", shape=(vectors.shape[0],), data=np.zeros((vectors.shape[0],), dtype=np.int32))
        f.create_dataset("notes", shape=(vectors.shape[0],), data=np.array(ips))

    print ("Finished prebuilding samples")
