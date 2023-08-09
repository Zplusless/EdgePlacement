import logging
import random
from datetime import datetime
from typing import List
# from Hop_delay_placement.edge_place_greedy_group import  GreedyGroup
from typing import Tuple

import numpy as np

from particle import Particle, Gbest
from base_station import BaseStation
from config import *
from edge_server import EdgeServer
from greedy_group import GreedyGroup
from utils import Random_Placement_Set

'''
按照以hop为距离进行运算
'''


class ServerPlacer(object):
    def __init__(self, all_base_stations: List[BaseStation], topology: List[List[float]]):
        self.all_base_stations = all_base_stations.copy()
        logging.info('载入基站信息，共有{0}个基站'.format(len(all_base_stations)))
        self.distance_topology = topology
        self.edge_servers = None

        # 价格计算参数
        self.maad = None
        self.ideal_delay = None
        self.max_payment = config_max_payment


    def place_server(self, base_station_num, edge_coverage):
        raise NotImplementedError

    def _distance_edge_server_base_station(self, edge_server: EdgeServer, base_station: BaseStation) -> float:
        """
        Calculate distance between given edge server and base station

        :param edge_server:
        :param base_station:
        :return: distance(km)
        """
        if edge_server.base_station_id is not None:
            return self.distance_topology[edge_server.base_station_id][base_station.id]
        else:
            print(edge_server, '\n\n', base_station)
            raise Exception('topology error')
            return 9999  # 如果不在拓扑中，默认为无限远

    def objective_latency(self):
        """
        Calculate average edge server access delay
        """
        assert self.edge_servers
        total_delay = 0
        base_station_num = 0
        for es in self.edge_servers:
            for bs in es.assigned_base_stations:
                delay = self._distance_edge_server_base_station(es, bs)
                logging.debug("base station={0}  delay={1}".format(bs.id, delay))
                total_delay += delay
                base_station_num += 1
        return total_delay / base_station_num

    def objective_workload(self):
        """
        用workload的标准差衡量负载均衡
        """
        assert self.edge_servers
        workloads = [e.workload for e in self.edge_servers]
        logging.debug("standard deviation of workload" + str(workloads))
        res = np.std(workloads)
        return res

    def objective_source_utilization(self):
        """计算平均资源利用率"""
        assert self.edge_servers
        sum = 0
        for e in self.edge_servers:
            sum += e.workload / EdgeServer.max_workload
        ans = sum / len(self.edge_servers)
        logging.debug("平均资源利用率" + str(ans))
        return ans

    def edge_sum(self):
        return len(self.edge_servers)

    def get_edge_list(self):
        '''
        :return: 返回edge的list
        '''
        return self.edge_servers

    def total_energy_consumption(self):
        total_energy = 0
        for edge in self.edge_servers:
            total_energy += self.workload_to_energy(edge.workload)
        return total_energy

    def total_profit(self):
        return self.get_total_profit()

    # ==========================================================================
    # SLA相关
    # ==========================================================================
    def workload_to_energy(self, workload):
        return 118.8 + workload * 59.4 / 3000000
        # return 106.92 + workload ** 2 * 1.1e-9

    # 当前连接情况
    def total_energy__delay_list(self):
        '''
        获取当前情况
        :return: total_energy，delay_list
        '''
        total_energy = 0
        delay_list = []
        # delay_not_record = [i for i in range(self.row)]  # 记录哪些bs的时延没有被登记
        for edge in self.edge_servers:
            total_energy += self.workload_to_energy(edge.workload)
            for bs in edge.assigned_base_stations:
                delay_list.append(self._distance_edge_server_base_station(edge, bs))
        # if len(delay_not_record)>0:
        #     raise Exception('delay list记录不完整')

        return total_energy, delay_list

    # 计算总耗电价格
    def get_total_energy_price(self, total_energy):
        # TODO: 确定电价
        total_energy_price = electircity_price*total_energy
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
            total_income += self.sla_regular(delay)*self.all_base_stations[bs_id].workload  # 单价 * 时长
        return total_income

    def get_total_profit(self):
        total_energy, delay_list = self.total_energy__delay_list()
        energy_price = self.get_total_energy_price(total_energy)
        sla_income = self.get_sla_income(delay_list)
        return sla_income-energy_price


class GreedyPlacer(ServerPlacer):
    def __init__(self, all_base_stations: List[BaseStation], topology: List[List[float]]):
        super().__init__(all_base_stations, topology)
        # self.base_station_to_place = []
        self.maad = 0  # 先初始化为0，后面会修改
        self.max_workload = 0

        # 所有未处理的edge的集合
        self.global_unattached_bs = []
        # 记录当前分组情况
        self.group_list: List[GreedyGroup] = []

    def place_server(self, base_station_num, maad):
        '''
        :param base_station_num: 基站列表
        :param maad: 规定的edge覆盖范围大小
        :return: 将edge的list赋值给  self.edge_servers
        '''
        logging.info("{0}:Start running Greedy with bs_num={1}, edge_coverage={2}".format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            base_station_num, maad))

        # 每次在不同参数下运行，先进行初始化
        self.group_list.clear()
        self.global_unattached_bs = self.all_base_stations[:base_station_num]
        self.max_workload = EdgeServer.max_workload

        # =======================sla计费模型参数赋值=============================
        self.maad = maad
        self.ideal_delay = delay_ratio * maad

        # 构建约束字典
        dict_limitations = {
            'workload': self.max_workload,
            'delay': self.maad,
            # 'total_price': self.MAX_TOTAL_PRICE,
            # 'load_balance': self.MAX_WORKOLAD_BALANCE
        }

        # 初始化，两两配对
        while self.global_unattached_bs:
            item_a, item_b = self.choose_pair_bs()
            # =====================================
            # print('[debug] init, choose_pair---->', id(item_a))
            # print('[debug] init, choose_pair---->', id(item_b))
            # =====================================
            temp_group = GreedyGroup(self.distance_topology, self.global_unattached_bs, dict_limitations, item_a,
                                     item_b)  # 一旦编入group，GreedyGroup构造函数会自动从self.global_unattached_edges中删除item
            self.group_list.append(temp_group)

        # 算法迭代
        while_flag_count = 0
        console_count = 0
        record_group = {}
        while while_flag_count < 10:  # 阈值设置为1，表示只要出现重复就跳出

            # while_flag_count += 1

            # 显示算法运行过程
            print('running greedy/while flag---->{}/{}'.format(console_count, while_flag_count))
            console_count += 1

            # last_group_list = deepcopy(self.group_list)

            # group合并
            pair_groups = self.choose_pair_groups()
            for pair in pair_groups:
                self.merge(*pair)
            self.refill()

            # 未分配的进行回填
            refill_times = 0
            print()
            while self.global_unattached_bs:  # 只要refill后还有没分配的，单独成堆
                print('回填次数---->', refill_times, '\r', end='')
                refill_times += 1

                item_a, item_b = self.choose_pair_bs()
                temp_group = GreedyGroup(self.distance_topology, self.global_unattached_bs, dict_limitations, item_a,
                                         item_b)  # 一旦编入group，GreedyGroup构造函数会自动从self.global_unattached_edges中删除item
                self.group_list.append(temp_group)

            # if len(last_group_list) == len(self.group_list):  # 如果group的列表不变，则计数加一。3个循环grouplist都不变，则结束
            #     print('出现相同结果')
            #     while_flag_count += 1
            # else:
            #     while_flag_count = 0

            while_flag_count += 1
            print('\n当前group个数{}'.format(len(self.group_list)))

            # 记录每次循环的结果
            # ***************************************************************
            # *原筛选方法
            # record_group[len(self.group_list)] = self.group_list  # 记录server数量，故优化server数量
            # *时延优先的筛选方法
            v = sum([g.get_max_delay() for g in self.group_list])/len(self.group_list)
            record_group[v] = self.group_list
            # ***************************************************************

        # 找出记录结果中的最小值
        min_key = min(record_group.keys())
        self.group_list = record_group[min_key]

        # 将group翻译成放置结果
        edge_servers = []
        for edge_id, group in enumerate(self.group_list):
            group.choose_core_node()
            core_bs = group.get_core_node()
            edge_temp = EdgeServer(edge_id, core_bs.latitude, core_bs.longitude, core_bs.id)
            edge_temp.workload = group.total_workload  # 初始化的时候只有所在基站的负载
            edge_temp.assigned_base_stations = group.this_group
            edge_servers.append(edge_temp)

        # 绑定结果，算法结束
        self.edge_servers = edge_servers

        #* ============================验证时延和负载没有超标======================================
        for edge in edge_servers:
            core_bs = edge.base_station_id
            for bs in edge.assigned_base_stations:
                if self.distance_topology[core_bs][bs.id] > self.maad:
                    if core_bs != bs.id:
                        print(f'{core_bs}--->{bs.id}:  {self.distance_topology[core_bs][bs.id]} ---> {self.maad}')
                        raise Exception('Greedy 违反时延约束')
                    # else:
                    #     print(f'违反时延约定，edge到自身bs：{core_bs}--->{bs.id}')
            
            if edge.workload > self.max_workload:
                print(f'违反workload约定：edge at {core_bs}')
                raise Exception('Greedy 违反负载约束')
        #  ============================验证时延没有超标======================================

        # ==============================验证bs分配状况==========================================
        recorded_bs = set([])
        for edge in self.edge_servers:
            for bs in edge.assigned_base_stations:
                recorded_bs.add(bs.id)
        if len(recorded_bs) != base_station_num:
            raise Exception('Greedy 未将所有bs正确分配')
        # ==============================验证bs分配状况==========================================

        logging.info("{0}:End running Random ".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # ========================================================================
    #                        place_server END!
    # ========================================================================

    def choose_pair_bs(self) -> Tuple:
        """
        只要self.global_unattached_bs非空，返回两个最近的edge
        :return:
        """
        if len(self.global_unattached_bs) > 1:
            p_a = self.global_unattached_bs[0]
            p_b = self.__get_nearest_node(p_a, self.global_unattached_bs)
            temp_delay = self.__get_delay(p_a, p_b)
            if temp_delay < self.maad and p_a.workload + p_b.workload <= self.max_workload:  # 满足时延约束和负载约束
                return p_a, p_b
            else:
                return p_a, None  # 不满足，只返回一个
        else:
            p_a = self.global_unattached_bs[0]
            return p_a, None

    def choose_pair_groups(self):
        """
        对 self.group_list中的group对象进行配对

        :return: pairs---->由配对的tuple组成的list，如果有落单的，single非None
        """
        pairs = []
        temp_group_list = [i for i in range(len(self.group_list))]
        while len(temp_group_list) > 0:
            if len(temp_group_list) > 1:  # 可以配对
                a_num = temp_group_list.pop()
                a = self.group_list[a_num]
                protential_b = [self.group_list[i] for i in temp_group_list]
                b = self.__get_nearest_node(a, protential_b)
                temp_group_list.remove(self.group_list.index(b))
                pairs.append((a, b))
            else:  # 只剩一个
                a_num = temp_group_list.pop()
                a = self.group_list[a_num]
                pairs.append((a, None))
        return pairs

    def merge(self, a: GreedyGroup, b: GreedyGroup):
        """
        :param a:
        :param b: b非None，a b合并，b为None，直接返回a
        :return: 输出合并的结果
        """

        # =====================================
        # print('start merge {} and {}'.format(a,b))
        # =====================================

        if b:  # 若b是非空，可以操作；若为None，不存在兼并的成对a,b，不操作
            win, lose = (a, b) if a.pk_value() >= b.pk_value() else (b, a)
            flag = False
            for item in lose.this_group:
                if win.can_absorb(item):
                    flag = True
                    break

            if flag:  # True---->存在可以插入的， 否则不可以插入，不操作
                lose_items = lose.dissolve()
                win.insert(lose_items)
                self.group_list.remove(lose)  # 从group列表中删除
                # 删除lose
                del lose

    def refill(self):
        """
        在所有的配对group都merge完之后，进行本操作
        :return:
        """
        # =====================================
        # print('start refill operation with unattached item---->{}'.format(self.global_unattached_edges))
        # =====================================

        for item in self.global_unattached_bs:
            for group in self.group_list:
                if group.can_absorb(item):
                    # =====================================
                    # print('Algorithm.global_unattached_edges---->', self.global_unattached_edges)
                    # =====================================
                    group.insert(item, self.global_unattached_bs)
                    break  # 防止item被吸收后，还要继续跟其它group比较

    def __get_nearest_node(self, item, item_list):
        """
        从itemlist中选择离item最近的

        :param item: edge或group
        :param item_list: list
        :return: edge或group
        """
        temp_dict = {}

        for i in item_list:
            temp_delay = self.__get_delay(item, i)
            if i is not item:
                if temp_delay not in temp_dict.keys():
                    temp_dict[temp_delay] = [i]  # 可以优化为随机选取
                else:
                    temp_dict[temp_delay].append(i)
        min_delay = min(temp_dict.keys())
        nearest_node = random.sample(temp_dict[min_delay], 1)[0]

        return nearest_node

    def __get_delay(self, a, b):
        if isinstance(a, BaseStation) and isinstance(b, BaseStation):
            return self.distance_topology[a.id][b.id]
        if isinstance(a, EdgeServer) and isinstance(b, EdgeServer):
            return self.distance_topology[a.base_station_id][b.base_station_id]
        if isinstance(a, GreedyGroup) and isinstance(b, GreedyGroup):
            return self.distance_topology[a.core_node.id][b.core_node.id]


class TopFirstPlacer(ServerPlacer):
    def __init__(self, all_base_stations: List[BaseStation], topology: List[List[float]]):
        super().__init__(all_base_stations, topology)
        self.base_station_to_place = []
        self.maad = 0  # 先初始化为0，后面会修改

    def place_server(self, base_station_num, maad):
        logging.info("{0}:Start running TopFirst with bs_num={1}, edge_coverage={2}".format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            base_station_num, maad))

        self.base_station_to_place = self.all_base_stations[:base_station_num]

        # =======================sla计费模型参数赋值=============================
        self.maad = maad
        self.ideal_delay = delay_ratio * maad

        edge_servers = []
        count_edge_id = 0

        sorted_base_stations = sorted(self.base_station_to_place, key=lambda x: x.workload)  # 从小到大排序，因为pop默认从末尾弹出

        while sorted_base_stations:  # 只要未放置的非空

            # 选择当前负载最大的作为edge
            bs_e = sorted_base_stations.pop()
            edge_temp = EdgeServer(count_edge_id, bs_e.latitude, bs_e.longitude, bs_e.id)
            count_edge_id += 1
            edge_temp.workload = bs_e.workload  # 初始化的时候只有所在基站的负载
            edge_temp.assigned_base_stations.append(bs_e)

            # 开始分配基站，采用首适应算法
            # 找出覆盖范围内的基站
            for station in sorted_base_stations:  # 这里的station就是一个bs对象
                distance = self._distance_edge_server_base_station(edge_temp, station)
                if distance <= self.maad:  # 在范围内就可以考虑
                    if station.workload + edge_temp.workload <= edge_temp.max_workload:
                        edge_temp.assigned_base_stations.append(station)  # 加入分配队列
                        edge_temp.workload += station.workload  # 更新edge负载
                        sorted_base_stations.remove(station)  # 从待放置集合中删除
                    else:  # 在距离内，但是edge负载已经超了
                        break
            # 将负载饱和的edge加入edge队列
            edge_servers.append(edge_temp)

        self.edge_servers = edge_servers

        # ==============================验证bs分配状况==========================================
        recorded_bs = set([])
        for edge in self.edge_servers:
            for bs in edge.assigned_base_stations:
                recorded_bs.add(bs.id)
        if len(recorded_bs) != base_station_num:
            raise Exception('Greedy 未将所有bs正确分配')
        # ==============================验证bs分配状况==========================================

        logging.info("{0}:End running TopFirst ".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))


class RandomPlacer(ServerPlacer):
    def __init__(self, all_base_stations: List[BaseStation], topology: List[List[float]]):
        super().__init__(all_base_stations, topology)
        self.base_station_to_place = []
        self.maad = 0  # 先初始化为0，后面会修改

    def place_server(self, base_station_num, maad):
        logging.info("{0}:Start running Random with bs_num={1}, edge_coverage={2}".format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            base_station_num, maad))

        self.base_station_to_place = self.all_base_stations[:base_station_num]

        # =======================sla计费模型参数赋值=============================
        self.maad = maad
        self.ideal_delay = delay_ratio * maad

        edge_servers = []
        count_edge_id = 0

        unplaced_set = Random_Placement_Set(base_station_num)
        while not unplaced_set.is_empty():

            # 初始化---随机选一个作为edge
            e = unplaced_set.pop()
            bs_e = self.base_station_to_place[e]
            edge_temp = EdgeServer(count_edge_id, bs_e.latitude, bs_e.longitude, bs_e.id)
            count_edge_id += 1
            edge_temp.workload = bs_e.workload  # 初始化的时候只有所在基站的负载
            edge_temp.assigned_base_stations.append(bs_e)

            # 开始分配基站，采用首适应算法
            # 找出覆盖范围内的基站
            for station in unplaced_set:
                if self.distance_topology[e][station] <= self.maad:  # 在范围内就可以考虑
                    if self.base_station_to_place[station].workload + edge_temp.workload <= EdgeServer.max_workload:
                        edge_temp.assigned_base_stations.append(self.base_station_to_place[station])  # 加入分配队列
                        edge_temp.workload += self.base_station_to_place[station].workload  # 更新edge负载
                        unplaced_set.remove(station)  # 从待放置集合中删除
                    else:  # 在距离内，但是edge负载已经超了
                        break
            # 将负载饱和的edge加入edge队列
            edge_servers.append(edge_temp)

        self.edge_servers = edge_servers

        # ==============================验证bs分配状况==========================================
        recorded_bs = set([])
        for edge in self.edge_servers:
            for bs in edge.assigned_base_stations:
                recorded_bs.add(bs.id)
        if len(recorded_bs) != base_station_num:
            raise Exception('Greedy 未将所有bs正确分配')
        # ==============================验证bs分配状况==========================================

        logging.info("{0}:End running Random ".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))


class PSOPlacer(ServerPlacer):
    def __init__(self, all_base_stations: List[BaseStation], topology: List[List[float]], particle_size, qpso):
        super().__init__(all_base_stations, topology)
        self.PARTICLE_SIZE = particle_size
        self.MAX_GENERATION = edge_placement_max_generation
        self.base_station_to_place = []
        # self.maad = 0  # 先初始化为0，后面会修改

        self.qpso = qpso

        # =========下方参数待定==============
        self.edge_MAX_WORKLOAD = EdgeServer.max_workload

        # 定义： 字典--->  {energy：xxx,   particle: 二维矩阵, edge_servers: {放置edge的bs的矩阵编号（不是id！）：总负载}}
        self.particles = []  # 元素是20个字典
        self.g_best :Gbest= None  # 一个元素,           修改元素的时候要用拷贝

        # # =========debug参数================
        # self.debug_count = 0
        # self.place_log = open(r'../data/place_log.txt', 'w')
        # self.edge_num_log = open(r'../data/edge_num.csv', 'w', newline='')

    def set_max_gen(self, max_gen=40):
        self.MAX_GENERATION = max_gen

    def place_server(self, base_station_num, maad):
        pso_name = 'QPSO' if self.qpso else 'PSO'
        logging.info("{0}:Start running {1} with bs_num={2}, edge_coverage={3}".format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            pso_name,
            base_station_num, 
            maad))

        # ==============每改变一次参数后要重新初始化的内容========================
        self.particles = []  # 元素是20个字典
        self.g_best = None
        self.base_station_to_place = self.all_base_stations[:base_station_num]

        # =======================sla计费模型参数赋值=============================
        self.maad = maad
        self.ideal_delay = delay_ratio * maad



        # 批量初始化
        self.particles = [Particle(i,
                                   self.base_station_to_place,
                                   self.distance_topology,
                                   self.maad,
                                   self.ideal_delay,
                                   self.max_payment,
                                   self.qpso)
                          for i in range(self.PARTICLE_SIZE)]

        # 更新pbest
        for p in self.particles:
            p.init_pbest()

        self.g_best = Gbest(self.particles)
        self.g_best.update()

        # # 记录初始化情况情况
        # debug_line = ['覆盖半径 ' + str(self.edge_coverage), '初始化']
        # for i_edge in range(self.PARTICLE_SIZE):
        #     # print('num = ', self.particles[i_edge]['num'], file=self.edge_num_log)
        #     debug_line.append(self.particles[i_edge]['num'])
        # debug_line.append(self.g_best['num'])
        # debug_edge_num.append(debug_line)
        # 演进操作
        # 开始演进

        # 更新粒子
        for generation in range(self.MAX_GENERATION):
            print(f"\n\n=============={pso_name}:   覆盖半径", self.maad, '  基站数目', base_station_num, "  第", generation,
                  "代==================")
            # print("\n\n==============覆盖半径", self.edge_coverage, '  基站数目', base_station_num, "  第", generation,"代========================", file=self.place_log)

            for particle in self.particles:
                state_code = particle.evolution(self.g_best)
                if state_code ==1:
                    # 不满足约束
                    self.edge_servers = []
                    return 0   # 提前结束

                # 更新pbest
                particle.update_pbest()

            self.g_best.update()

        #     # 记录粒子情况
        #     debug_line = ['覆盖半径 ' + str(self.edge_coverage), '代数 ' + str(generation)]
        #     for i_edge in range(self.PARTICLE_SIZE):
        #         # print('num = ', self.particles[i_edge]['num'], file=self.edge_num_log)
        #         debug_line.append(self.particles[i_edge]['num'])
        #     debug_line.append(self.g_best['num'])
        #
        #     debug_edge_num.append(debug_line)
        #
        # debug_edge_num.append([])

        # debug_csv_writer = csv.writer(self.edge_num_log)
        # debug_csv_writer.writerow(debug_edge_head)
        # debug_csv_writer.writerows(debug_edge_num)

        print()
        # 把结果翻译成标准输出
        edge_servers = []
        count_edge_id = 0

        placement_scheme = self.g_best.placement_scheme
        for edge in placement_scheme:
            at_bs = self.base_station_to_place[edge['at_bs_No']]
            edge_temp = EdgeServer(count_edge_id, at_bs.latitude, at_bs.longitude, edge['at_bs_No'] )
            edge_temp.workload = edge['workload']
            edge_temp.assigned_base_stations = edge['serving_bs']
            count_edge_id+=1
            edge_servers.append(edge_temp)

        self.edge_servers = edge_servers

        # self.place_log.close()
        logging.info("{0}:End running {1} ".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), pso_name))

    # ============================= place_server  end ========================================

    # 初始化放置,包括粒子、pbest、gbest的初始化
    # def init(self, base_station_num, particle):
    #
    #     edge_count = 0
    #
    #     unplaced_set = Random_Placement_Set(base_station_num)
    #     # unplaced_set = Sorted_BaseStation_Set(self.base_station_to_place, base_station_num)
    #
    #     matrix = [[False for i in range(base_station_num)] for j in range(base_station_num)]
    #     edge_workload = {}
    #
    #     # 只要未放置集合非空
    #     while not unplaced_set.is_empty():
    #
    #         edge_count += 1
    #
    #         # 放置边缘服务器
    #         e = unplaced_set.pop()
    #         matrix[e][e] = True  # 先将这个标记成已经放置
    #
    #         # 待绑定的基站
    #         candidates = {}
    #         candidates_total_workload = 0
    #
    #         # 找出覆盖范围内的基站
    #         for station in unplaced_set:
    #             if self.distance_topology[e][station] <= self.maad:  # 在范围内就加入备选序列
    #                 candidates[station] = 0  # 初始化
    #                 candidates_total_workload += self.base_station_to_place[station].workload  # 计算范围内的基站的总负载
    #
    #     # =============================采用Q初始化===================================
    #         # 计算排序权重
    #         for k in candidates.keys():
    #             # 防止有0距离
    #             # if self.distances[e][k] == 0:
    #             #     self.distances[e][k] = DataUtils.calc_distance(self.base_station_to_place[e].latitude, self.base_station_to_place[e].longitude, self.base_station_to_place[k].latitude,
    #             #                                                          self.base_station_to_place[k].longitude)
    #
    #             if self.distance_topology[e][k] * candidates_total_workload > 0:
    #                 candidates[k] = (self.maad / self.distance_topology[e][k]) + (
    #                             self.base_station_to_place[k].workload / candidates_total_workload)
    #
    #         # 按权重排序
    #         sorted_canditates = dict(sorted(candidates.items(), key=lambda d: d[1], reverse=True))
    #     # ==========================================================================
    #     #     # 不采用Q初始化
    #     #     sorted_canditates = candidates
    #
    #         # 开始修改矩阵，给edge分配bs
    #         edge_temp_workload = self.base_station_to_place[e].workload
    #         for bs in sorted_canditates.keys():
    #             bs_i = bs  # bs_i 仅仅是编码矩阵中的位置，并非基站id
    #             if self.base_station_to_place[bs_i].workload + edge_temp_workload <= self.edge_MAX_WORKLOAD:
    #                 matrix[bs_i][e] = True
    #                 unplaced_set.remove(bs_i)
    #                 edge_temp_workload += self.base_station_to_place[bs_i].workload
    #
    #         # 记录edge的负载
    #         edge_workload[e] = edge_temp_workload
    #
    #     print('初始化完成，放置edge节点个数:', edge_count)
    #     # print('length of edge_workload:', len(edge_workload))
    #
    #     # 将初始化结果写入particle
    #     particle['num'] = edge_count
    #     particle['matrix'] = matrix
    #     particle['edge_workload_dict'] = edge_workload
    #     particle['total_energy'] = self._cal_energy(edge_workload)
    #     particle['diagonal'] = [matrix[i][i] for i in range(len(matrix))]

    def total_profit(self):
        return self.g_best.profit

