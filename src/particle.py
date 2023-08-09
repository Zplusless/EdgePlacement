from utils import Random_Placement_Set
import numpy as np
from edge_server import EdgeServer
from base_station import BaseStation
from typing import List
from utils import DataUtils
import random
from config import *
from copy import deepcopy


class Particle(object):

    def __init__(self, particle_id: int, bs_list: List[BaseStation], distances: List[List[float]], maad, ideal_delay, max_payment, qpso = False):

        #  自身数据
        self.id = particle_id
        self.bs_list = bs_list
        self.distance_topology = distances
        self.row = len(bs_list)
        self.col = len(bs_list)

        self._matrix = []
        self.V = []
        self.pbest = {}

        # 电费
        self.electric_price = electircity_price

        # ===============可变参数=========================
        self.edge_max_workload = EdgeServer.max_workload
        self.maad = maad
        self.ideal_delay = ideal_delay
        self.max_payment = max_payment
        self.qpso = qpso

        # ===============粒子初始化=======================
        self.randam_init()

    def randam_init(self):
        self._matrix = [[False for i in range(self.col)] for j in range(self.row)]
        # 速度向量随机初始化
        self.V = [True if random.random() < 0.5 else False for i in range(self.row)]
        # 产生随机序列
        unplaced_set = Random_Placement_Set(self.row)
        # 只要未放置集合非空
        while not unplaced_set.is_empty():

            # 放置edge
            bs_id_of_placed_edge: int = unplaced_set.choose() # 此处不能pop，否则如果被替换，则再也不会被分配

            #* 不急着标记
            # self._matrix[bs_id_of_placed_edge][bs_id_of_placed_edge] = True  # 先将这个标记成已经放置



            # ==========================================================================
            #                                  配套非归一化Q
            # --------------------------------------------------------------------------
            # 待绑定的bs
            candidates = {}
            candidates_total_workload = 0.1  # 因为存在负载为0的bs，故从1开始加，这一点负载不影响结果
            # 找出覆盖范围内的bs
            for unplaced_bs in unplaced_set:
                if self.get_bs_distance(bs_id_of_placed_edge, unplaced_bs) <= self.maad:  # 在范围内就加入备选序列
                    candidates[unplaced_bs] = 0  # 初始化
                    candidates_total_workload += self.bs_list[unplaced_bs].workload  # 计算范围内的基站的总负载
            
            #******************************************************************
            #* 新加的，借鉴greedy中，对一个团的item选这一群中的最好的
            #* 因为之前的那个不一定是最合适做edge的
            try:
                candidates[bs_id_of_placed_edge] = 0
                min_maxDelay = 99999
                for bs in candidates.keys():
                    delay_distances = [self.get_bs_distance(bs, bbss) for bbss in candidates.keys()]
                    max_d_of_bs = max(delay_distances)
                    if max_d_of_bs < min_maxDelay:
                        min_maxDelay = max_d_of_bs
                        bs_id_of_placed_edge = bs
                
                
                candidates.pop(bs_id_of_placed_edge)
                unplaced_set.remove(bs_id_of_placed_edge) # 此处要删除，否则陷入死循环
            except Exception as e:
                print('\n\n*************************')
                print(e)
                print('\n\n*************************')
                exit(-1)
            #******************************************************************
            # 先将这个edge标记成已经放置
            self._matrix[bs_id_of_placed_edge][bs_id_of_placed_edge] = True  # 这一行保留，不用删除


            if self.qpso:
                # # # ===按照Q初始化=========================================================
                # # 计算排序权重
                for k in candidates.keys():

                    distance_k = self.get_bs_distance(bs_id_of_placed_edge, k)

                    # 权重计算公式
                    if distance_k * candidates_total_workload > 0:
                        #*************************************
                        idea_delay = delay_ratio*self.maad
                        if distance_k < idea_delay:
                            distance_k = distance_k / 10
                        #*************************************
                        candidates[k] = (self.maad / distance_k) + (
                                self.bs_list[k].workload / candidates_total_workload)
                    else:
                        print('edge_bs---->{},    candidates_bs---->{}'.format(bs_id_of_placed_edge, k))
                        print('distance_k:', distance_k)
                        print('candidates_total_workload:', candidates_total_workload)
                        raise Exception('Q排序出错')

                # 按权重排序
                sorted_canditates = dict(sorted(candidates.items(), key=lambda d: d[1], reverse=True))
                # # # ==========================================================================
            else:
                # ===不按Q初始化===========================================================
                sorted_canditates = candidates
                # ========================================================================


            # 开始修改矩阵，给edge分配bs
            edge_temp_workload = self.bs_list[bs_id_of_placed_edge].workload
            for e in sorted_canditates.keys():
                if self.bs_list[e].workload + edge_temp_workload <= self.edge_max_workload:
                    self._matrix[e][bs_id_of_placed_edge] = True   # 标记放置
                    unplaced_set.remove(e)
                    edge_temp_workload += self.bs_list[e].workload
        
            #******************
            # print('未放置数目还剩：{}'.format(len(unplaced_set.list)))
    # ================================end of __init()__========================================================

    # 计算两个edge的距离
    def get_edge_distance(self, edge1: int, edge2: int):
        edge1_bs = self.bs_list[edge1].id
        edge2_bs = self.bs_list[edge2].id
        return  self.distance_topology[edge1_bs][edge2_bs]

    # 计算连个基站之间的距离
    def get_bs_distance(self, bs1, bs2):
        return self.distance_topology[bs1][bs2]

    # # 返回 服务的总数目
    # def get_service_num(self):
    #     count = 0
    #     for i in range(self.row):
    #         if self._matrix[i][i]:
    #             count += 1
    #     return count
    #
    # # 某一列，是service的话返回当前的负载，不是返回0
    # def get_workload_of_service_i(self, i):
    #     if not self._matrix[i][i]:
    #         return 0
    #     else:
    #         temp = 0
    #         for line in range(self.row):
    #             if self._matrix[line][i]:
    #                 temp += self.bs_list[line].workload
    #         return temp
    #
    # # 查看当前放置方案(哪些edge放了service，每个service服务哪些edge，service的负载)
    # def get_condition(self):
    #     condition = []
    #
    #     # 逐列遍历
    #     for i in range(self.col):
    #         edge = self._matrix[i][i]
    #         service_workload_temp = 0
    #         edge_list_temp = []
    #
    #         if edge:
    #             for j in range(self.row):
    #                 if self._matrix[j][i]:
    #                     service_workload_temp += self.bs_list[j].workload
    #                     edge_list_temp.append(j)
    #             dict_temp = {'location': i, 'serving_edges': edge_list_temp, 'workload': service_workload_temp}
    #             condition.append(dict_temp)
    #     return condition
    #
    # # 计算负载均衡
    # def get_workload_balance(self):
    #     workloads = [e['workload'] for e in self.get_condition()]
    #     ans = np.std(workloads)
    #     return ans

    # 计算平均时延
    def get_average_delay(self, delay_list):
        return sum(delay_list)/len(delay_list)

    # 某一列，是service的话返回当前的负载，不是返回0
    def get_workload_of_edge_i(self, i):
        if not self._matrix[i][i]:
            return 0
        else:
            temp = 0
            for line in range(self.row):
                if self._matrix[line][i]:
                    temp += self.bs_list[line].workload
            return temp

    # 查看当前放置方案(哪些edge放了service，每个service服务哪些edge，service的负载)
    def get_condition(self):
        condition = []

        # 逐列遍历
        for i in range(self.col):
            bs = self._matrix[i][i]
            edge_workload_temp = 0
            bs_list_temp = []

            if bs:
                for j in range(self.row):
                    if self._matrix[j][i]:
                        edge_workload_temp += self.bs_list[j].workload
                        bs_list_temp.append(self.bs_list[j])
                dict_temp = {'at_bs_No': i, 'serving_bs': bs_list_temp, 'workload': edge_workload_temp}
                condition.append(dict_temp)
        return condition

    # ==========================================================================
    # SLA相关
    # ==========================================================================
    def workload_to_energy(self, workload):
         return 118.8 + workload * 59.4 / 3000000
        # return 106.92 + workload**2*1.1e-9

    # 当前连接情况
    def total_energy__delay_list(self):
        '''
        获取当前情况
        :return: total_energy，delay_list
        '''
        total_energy = 0
        delay_list = [-1 for k in range(self.row)]
        delay_not_record = [i for i in range(self.row)]  # 记录哪些bs的时延没有被登记
        for i in range(self.row):
            if self._matrix[i][i]:  # 如果是edge
                load_temp = 0
                for j in range(self.row):
                    if self._matrix[j][i]:
                        load_temp += self.bs_list[j].workload
                        delay_list[j] = self.get_bs_distance(j,i)
                        delay_not_record.remove(j)
                total_energy += self.workload_to_energy(load_temp)
                # print(total_energy)
        if len(delay_not_record)>0:
            raise Exception('delay list记录不完整')

        return total_energy, delay_list

    # 计算总耗电价格
    def get_total_energy_price(self, total_energy):
        # TODO: 确定电价
        total_energy_price = self.electric_price*total_energy
        return total_energy_price

    # SLA规则
    def sla_regular(self, delay):
        if delay < 0:
            raise ValueError('delay为负')
        return self.max_payment if delay < self.ideal_delay else self.max_payment - (delay-self.ideal_delay)/(self.maad-self.ideal_delay)*self.max_payment

    # SLA计价
    def get_sla_income(self, delay_list):
        total_income = 0
        for bs_id, delay in enumerate(delay_list):
            total_income += self.sla_regular(delay)*self.bs_list[bs_id].workload  # 单价 * 时长
        return total_income

    def get_total_profit(self):
        total_energy, delay_list = self.total_energy__delay_list()
        energy_price = self.get_total_energy_price(total_energy)
        sla_income = self.get_sla_income(delay_list)
        return sla_income-energy_price




    # 获得对角线，得到速度V
    def get_diagonal(self):
        ans = [self._matrix[i][i] for i in range(self.col)]
        return ans

    # # 初始化pbest
    def init_pbest(self):
        # pbest是none或者新的时延更小时
        # {'matrix':[[]], 'V': [], 'condition': {}, 'workload_balance': float, 'total_price': int, 'average_delay': int}

        total_energy, delay_list = self.total_energy__delay_list()
        self.pbest['total_energy'] = total_energy
        self.pbest['matrix'] = deepcopy(self._matrix)
        self.pbest['service_state'] = self.get_diagonal()
        self.pbest['average_delay'] = self.get_average_delay(delay_list)
        self.pbest['profit'] = self.get_total_profit()




    # 更新pbest
    def update_pbest(self):

        # ===========================优化profit==========================================
        if self.pbest['profit'] < self.get_total_profit():   # profit大了，更新pbest
            total_energy, delay_list = self.total_energy__delay_list()
            self.pbest['total_energy'] = total_energy
            self.pbest['matrix'] = deepcopy(self._matrix)
            self.pbest['service_state'] = self.get_diagonal()
            self.pbest['average_delay'] = self.get_average_delay(delay_list)
            self.pbest['profit'] = self.get_total_profit()
        elif self.pbest['profit'] == self.get_total_profit(): # profit相等，优化时延小或者能耗小的
            total_energy, delay_list = self.total_energy__delay_list()
            current_average_delay = self.get_average_delay(delay_list)
            if self.pbest['average_delay'] > current_average_delay or self.pbest['total_energy']>total_energy:
                self.pbest['total_energy'] = total_energy
                self.pbest['matrix'] = deepcopy(self._matrix)
                self.pbest['service_state'] = self.get_diagonal()
                self.pbest['average_delay'] = self.get_average_delay(delay_list)
                self.pbest['profit'] = self.get_total_profit()
        # ===========================优化profit==========================================

        # # ===========================优化delay==========================================
        # total_energy, delay_list = self.total_energy__delay_list()
        # current_average_delay = self.get_average_delay(delay_list)
        # if self.pbest['average_delay'] > current_average_delay:
        #     self.pbest['total_energy'] = total_energy
        #     self.pbest['matrix'] = deepcopy(self._matrix)
        #     self.pbest['service_state'] = self.get_diagonal()
        #     self.pbest['average_delay'] = self.get_average_delay(delay_list)
        #     self.pbest['profit'] = self.get_total_profit()
        # # ===========================优化delay==========================================


    # 检查粒子是否合法，分别按照行列检查， ！！！仅检查放置的唯一性！！！
    # 返回出错的行号
    def check_particles(self):
        wrong_lines = set([])
        # 按行遍历
        for row in range(self.row):
            count = 0
            to_delete = False
            for col in range(self.col):
                if self._matrix[row][col]:
                    count += 1
                    # 检查是否连在有效edge上
                    if not self._matrix[col][col]:
                        # count = 999
                        to_delete = True
                        break
                    if count > 1:
                        # to_delete = True
                        break
            if count != 1:  # 0个或超过1个都不行
                to_delete = True
            # 对有标记的行加入删除集合
            if to_delete:
                wrong_lines.add(row)
                # 如果要删除的是edge，则连到它的都删除
                if self._matrix[row][row]:
                    for line in range(self.row):
                        if self._matrix[line][row]:
                            wrong_lines.add(line)
        return wrong_lines

    # 删除与回填操作
    def del_and_refill(self, wrong_lines):

        # 删除操作
        for line in wrong_lines:
            self._matrix[line] = [False for i in range(self.col)]

        # 获取当前particle状态
        service_state = self.get_diagonal()

        # 回填
        for line in wrong_lines:
            this_line_is_refilled = False

            # 先找现有的edge看能否接入
            for e in range(self.row):
                if service_state[e]:
                    # 负载不超标 且 在覆盖范围内
                    if (self.get_workload_of_edge_i(e) + self.bs_list[line].workload < self.edge_max_workload) \
                            and (self.get_edge_distance(e, line) < self.maad):
                        self._matrix[line][e] = True
                        this_line_is_refilled = True
                        break

            # 如果没有现有的可用，就在该edge新放置一个service
            if not this_line_is_refilled:
                self._matrix[line][line] = True

    # 更新粒子
    def evolution(self, gbest):
        # particle_now = deepcopy(self._matrix)

        t1 = self.get_total_profit()
        t2 = self.pbest['profit']
        t3 = gbest.profit


        t_min = min(t1, t2, t3)
        
        # 保证最后的tt1~tt3是正的
        if t_min > 0 :
            t_min = t_min * 0.8
        else:
            t_min = t_min * 1.2

        tt1 = (t1 - t_min)
        tt2 = (t2 - t_min)
        tt3 = (t3 - t_min)
        t_123 = tt1 + tt2 + tt3

        p1 = tt1 / t_123
        p2 = tt2 / t_123
        p3 = tt3 / t_123
        print('{:<11.10},  {:<11.10},   {:<11.10},  {}'.format(t1, t2, t3, '<----' if t1==t3 or t2==t3 else '     '), end='')
        print(' {:<8.6},  {:<8.6},  {:<8.6}'.format(p1,p2,p3))

        if p1 < 0.2:
            self.randam_init()
        else: # 按照正常的杂交更新
            if srv_print_log:
                print('粒子No.{0}更新速度，p1={1}, p2={2}, p3={3}'.format(self.id, p1, p2, p3))

            # 更新速度
            for i in range(self.col):
                r = random.random()
                if r <= p1:
                    continue
                elif (r > p1) and (r <= p2 + p1):
                    self.V[i] = not (self.pbest['service_state'][i] == self.get_diagonal()[i])
                else:
                    self.V[i] = not gbest.service_state[i] == self.get_diagonal()[i]

            # 更新matrix
            for i in range(self.col):
                if self.V[i]:
                    r = random.random()
                    if r < p1:
                        continue
                    if (r > p1) and (r <= p2 + p1):
                        for line in range(self.row):
                            self._matrix[line][i] = self.pbest['matrix'][line][i]
                    else:
                        for line in range(self.row):
                            self._matrix[line][i] = gbest.matrix[line][i]
            # 检查错误
            wrong_lines = self.check_particles()

            # 删除&回填
            self.del_and_refill(wrong_lines)

        return 0


class Gbest(object):
    def __init__(self, particles: List[Particle]):
        self.particles = particles

        self.matrix = None
        self.service_state = None
        self.condition = None
        self.average_delay = 999
        self.profit = -1000000000000
        self.placement_scheme = None

    def update(self):
        # temp_particle_for_sort = sorted(self.particles, key=lambda d: d.pbest['average_delay'])
        temp_particle_for_sort = sorted(self.particles, key=lambda d: d.pbest['profit'], reverse = True)

        # particles.sort(key=lambda d: d.pbest['average_delay'])
        best_particle = temp_particle_for_sort[0]

        # if best_particle.pbest['average_delay'] < self.average_delay:  # 优化时延
        if best_particle.pbest['profit'] > self.profit:  # 优化利润
            self.matrix = deepcopy(best_particle.pbest['matrix'])
            self.service_state = deepcopy(best_particle.pbest['service_state'])
            self.average_delay = best_particle.pbest['average_delay']
            self.profit = best_particle.pbest['profit']
            self.placement_scheme = best_particle.get_condition()

            # 防止该粒子停止不动
            best_particle.randam_init()

        # 检查profit是否一直都是在增大
        elif best_particle.pbest['profit'] < self.profit:
            print('error: gbest 在减小:      ', self.profit,'---->', best_particle.pbest['profit'])
            raise ValueError('Gbest profit getting smaller')

