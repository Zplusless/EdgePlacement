from typing import Dict

from algorithms_hop import *
from utils import *
import csv
import pickle
from data_process.generate_topology import generate_topology, DelayProcess, UPF_path
import pickle

from config import *
import time

import numpy as np


from multiprocessing import Process, Pool, Manager
from pprint import pprint

'''
按照以hop为距离进行运算

四个算法同时跑
'''

def repeat_operation(problem:ServerPlacer, repeat:int, n, k):
    ave_delay = []
    ave_total_profit = []
    ave_total_energy = []
    ave_resource_util = []
    ave_edge_num = []

    mean = {}
    std = {}

    p = Pool()
    with Manager() as m:
        # d = m.dict()
        d = {}
        # 对同一算法的不同批次重复运算进行并行处理
        for t in range(repeat):
            # p.apply_async(run_problem, args = (problem, n, k, d, t))
            run_problem(problem, n, k, d, t)

        p.close()
        p.join() # 等待所有进程都算完

        ave_delay=[d[i][0] for i in range(repeat)]
        ave_total_profit=[d[i][1] for i in range(repeat)]
        ave_total_energy=[d[i][2] for i in range(repeat)]
        ave_resource_util=[d[i][3] for i in range(repeat)]
        ave_edge_num=[d[i][4] for i in range(repeat)]

    mean['delay'] = np.mean(ave_delay)
    mean['profit'] = np.mean(ave_total_profit)
    mean['energy'] = np.mean(ave_total_energy)
    mean['util'] = np.mean(ave_resource_util)
    mean['edge_num'] = np.mean(ave_edge_num)

    std['delay'] = np.std(ave_delay)
    std['profit'] = np.std(ave_total_profit)
    std['energy'] = np.std(ave_total_energy)
    std['util'] = np.std(ave_resource_util)
    std['edge_num'] = np.std(ave_edge_num)
    return mean, std
    # return sum_a / repeat, sum_b / repeat, sum_c / repeat, sum_d / repeat, sum_bs / repeat, res[5]

def run_problem(problem: ServerPlacer, n, k, result, i):
    assert hasattr(problem, "place_server")
    problem.place_server(n, k)
    result[i] = [problem.objective_latency(), 
                problem.total_profit(), 
                problem.total_energy_consumption(), 
                problem.objective_source_utilization(), 
                problem.edge_sum(), 
                problem.get_edge_list()]

    return (problem.objective_latency(), problem.total_profit(), problem.total_energy_consumption(), problem.objective_source_utilization(), problem.edge_sum(), problem.get_edge_list())


def run_with_parameters(problems: Dict[str, ServerPlacer], n, k):
    # 最终返回结果中的顺序，同加入字典的顺序
    # if not isinstance(results, DictProxy):
    #     raise Exception('没有传入result字典')
    repeat = None
    temp = {}
    for alg, problem in problems.items():
        if 'PSO' in alg:
            repeat = pso_repeat
        else:
            repeat = 6
        
        mean, std = repeat_operation(problem, repeat, n, k)
       
        # lock.acquire()
        # temp = results
        if alg not in temp.keys():
            temp[alg] = {}
        
        # if f'{n}_{k}' not in temp[alg].keys(): 
        temp[alg] = {'mean':mean, 'std':std}
        # temp = {'mean':mean, 'std':std}
        # results = temp 
        # lock.release()

    with open(f'../result/result_{n}_{k}', 'wb') as f:
        # pickle.dump(temp, f)
        pickle.dump(temp, f)

    return temp
        


def run(data: DataUtils, delay_matrix :List[List[float]]):

    problems = {}
    problems['TopFirst'] = TopFirstPlacer(data.base_stations, delay_matrix)
    problems['Random'] = RandomPlacer(data.base_stations, delay_matrix)

    # 粒子种群大小
    particle_size = 10

    
    problems['QPSO'] = PSOPlacer(data.base_stations, delay_matrix, particle_size, qpso=True)
    problems['PSO'] = PSOPlacer(data.base_stations, delay_matrix, particle_size, qpso=False)
    problems['Greedy'] = GreedyPlacer(data.base_stations, delay_matrix)


    # 留出时间看上面的结果
    time.sleep(5)
    

    
    final_result = {}


    #***************************
    #*   选择变化量
    #***************************
    is_k_change = True
    k_values =  (5, 6) # (2,9) if is_k_change else (3,4)
    n_values =  (500, 600, 200)  # (1100, 1200, 200) if is_k_change else (300, 1400, 200)
    kn = 'k' if is_k_change else 'n' 

    for k in range(*k_values):
        for n in range(*n_values):
            # n---->基站数目， k---->基站半径
            # p = Process(target=run_with_parameters, args=(problems, n, k, results))
            # p.start()
            # run_with_parameters(problems, n, k, results=results)

            # for d in results.values():
                # d[(n,k)] = manager.dict()
            
            # pool.apply_async(run_with_parameters, args=(problems, n, k, results, lock))
            final_result[(n,k)] = run_with_parameters(problems, n, k)

    # pool.close()
    # pool.join()

    with open(r'../result/final_result_'+kn, 'wb') as f:
        pickle.dump(final_result, f)
        pprint(final_result)
        # pprint(results['PSO'])




if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    if edge_placement_max_generation >400:
        raise Exception('迭代次数太大，注意这里不是迭代测试')


    start_time = "start run at: {0}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    print('开始边缘放置，topology---->max_link:{}  max_dis:{}'.format(max_link, max_dis))
    time.sleep(2)

    # print('是否使用Q-PSO：', qpso)

    data = DataUtils('../data/基站经纬度_修改完整版_增加缺失地址_修改重复地址.csv', '../data/上网信息输出表（日表）7月15号之后.csv')
    topology = generate_topology(data)
    delay_data = DelayProcess(r'../data/measure0.2')
    ave_delay = delay_data.get_ave_delay()

    upath = UPF_path(topology, 3, 100, ave_delay)
    run(data, upath.delay_matrix)

    end_time = "end run at:{0}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    print('\n\n\n')
    logging.info(start_time)
    logging.info(end_time)
