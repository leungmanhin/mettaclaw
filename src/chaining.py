import time
import queue
import multiprocessing
from semantic_parsing import petta_chainer_handler

def _main_chain(query, result_queue, handler, max_depth):
    depth = 0
    result = []
    start_time = time.time()
    print(f"... chaining for: {query}")
    try:
        while ((not result) and (depth < max_depth)):
            depth += 1
            print(f"... chaining with depth = {depth}")
            result = handler.query(query, depth=depth)
    except Exception as e:
        print(f"\n!!! EXCEPTION: {e}\n")

    end_time = time.time()
    print(f"Chaining result: {result}\n(Time used: {end_time - start_time} seconds)\n")
    result_queue.put(result)

def chain(query, timeout=10, max_depth=6):
    result = []
    chaining_return_queue = multiprocessing.Queue()

    chaining_process = multiprocessing.Process(
        target = _main_chain,
        args = (query, chaining_return_queue, petta_chainer_handler, max_depth)
    )

    chaining_process.start()

    try:
        result = chaining_return_queue.get(timeout=timeout)
    except queue.Empty:
        pass

    chaining_process.join(timeout=1)

    if chaining_process.is_alive():
        print(f"... chaining_process is taking too long (>= {timeout} seconds), terminating")
        chaining_process.terminate()
        chaining_process.join()
        print("... chaining_process terminated")

    return result

def chain_queries(queries):
    all_results = []
    for query in queries:
        all_results += chain(query)
    return all_results
