import logging
import pickle
from datetime import datetime
from typing import List, Dict

import config
from base_station import BaseStation
from data_process.generate_topology import generate_topology
from edge_server import EdgeServer
from utils import DataUtils


# 定义greedy算法中的组



class GreedyGroup(object):
    # 初始化，将a和b合成堆, 定义存储list
    def __init__(self, topology: List[List[float]], unattached_list: List, limitations: Dict, item_a, item_b=None):  # item_list引入greedy算法类的itemlist
        """
        :param topology: 基站拓扑
        :param unattached_list: GreedAlgorithm中维持的判定是否放置的list
        :param item_a: 待融合edge A
        :param item_b: 待融合edge B
        """
        # 预判放置的是不是处于未放置队列

        self.topology = topology
        self.this_group = []  # 存放bs或edge
        self.global_unattached_list = unattached_list
        self.core_node = None
        self.max_delay = None
        self.total_workload = None

        # 记录约束条件
        self.workload_limit = limitations['workload']
        self.delay_limit = limitations['delay']

        if item_b is not None:   # b不是None, 合并
            if item_a in self.global_unattached_list and item_b in self.global_unattached_list:
                if item_a.workload + item_b.workload < self.workload_limit:  # 可以省去这一行，已经在choose_pair中检查过了
                    self.this_group.append(item_a)
                    self.this_group.append(item_b)
                    self.global_unattached_list.remove(item_a)
                    self.global_unattached_list.remove(item_b)
                    self.choose_core_node()
                else:
                    print('\n\n=====================================\n出现workload超标问题！！！！')
                    raise Exception('workload exceeded')
            else:
                print('error---->将已归组的节点(a/b)重新归组')
                raise Exception
        else:   # a单独成堆
            if item_a in self.global_unattached_list:
                self.this_group.append(item_a)
                self.global_unattached_list.remove(item_a)
                self.choose_core_node()
            else:
                print('error---->将已归组的节点a重新归组')
                raise Exception

        # 计算总负载
        temp_workload = 0
        for item in self.this_group:
            temp_workload += item.workload
        self.total_workload = temp_workload

        # 保证self.total_workload不超标
        if self.total_workload > self.workload_limit:
            raise Exception('初始化结束，负载超标')


        # 保证self.max_delay不为None
        if self.max_delay is None:
            print('item_a和item_b的距离：  ',self.topology[item_a.id][item_b.id])
            print('init失败，self.max_delay 为 None。未放置item还剩---->', len(self.global_unattached_list))
            print('item_a---->\n', item_a)
            print('item_b---->\n', item_b)

            raise Exception

    def __str__(self):
        ans = []
        for item in self.this_group:
            ans.append(item.id)
        return 'Group Info ----> '+str(ans)

    # 插入元素，用于a b PK结束后，吸收被打散的那个
    def insert(self, free_items, unattached_edge=None):
        """
        :param free_items: 待插入的节点
        :return: True---->成功插入， False---->超出负载
        """
        if not isinstance(free_items, List):
            free_items = [free_items]

        for item in free_items:
            if item not in self.global_unattached_list:
                print('error---->将已归组的节点插入新的组')
                # =====================================
                print('GreedyGroup.global_unattached_list---->', self.global_unattached_list)
                print('Algorithm.global_unattached_edges <----> GreedyGroup.global_unattached_list', self.global_unattached_list is unattached_edge)
                print('item---->', item)
                print('free_items---->', free_items)
                # =====================================
                raise Exception
            else:
                if self.__get_delay(self.core_node, item) < self.delay_limit:    # 保证时延约束
                    if self.total_workload + item.workload <= self.workload_limit:    # 保证负载约束
                        self.this_group.append(item)
                        self.global_unattached_list.remove(item)
                        self.total_workload += item.workload    # 计入负载增加量


        # 将可以兼并的节点插入后，重新规划core_node
        self.choose_core_node()

        # 计算总负载
        temp_workload = 0
        for item in self.this_group:
            temp_workload += item.workload

        # 验证负载有没有计算错误
        if temp_workload != self.total_workload:
            print('insert失败，负载不一致')
            raise Exception('incert失败，负载不一致')

        if self.total_workload > self.workload_limit:
            print('insert失败，负载超标')
            print([i.id for i in self.this_group ])
            raise Exception('incert失败，负载超标')

        # 保证self.max_delay不为None
        if self.max_delay is None:
            print('insert失败，self.max_delay 为 None')
            raise Exception

    # PK失败后，用于解散本group
    def dissolve(self):
        """
        :return:
        """
        this_group = self.this_group
        self.global_unattached_list.extend(this_group)
        # self.this_group.clear()  # 本组清空
        return this_group

    # 选择核心节点（放置点）
    def choose_core_node(self):
        """
        将各个节点按照与本组中其它节点的delay的最大值排序
        选取该值最小的为core_node,即放置点
        """
        if len(self.this_group) == 0:
            raise Exception('对空group选择core node')

        if len(self.this_group) > 1:
            dict_max_delay = {}  # {节点id：节点的最大距离}
            for item in self.this_group:
                # =====================================
                # print('[debug] choose_core_node---->',id(item))
                # =====================================

                # 找出每个节点与本组中其它节点距离的最大值
                delays = [self.__get_delay(item, other) for other in self.this_group]
                max_delay_of_item = max(delays)
                dict_max_delay[max_delay_of_item] = item

            min_max_delay = min(dict_max_delay.keys())  # 找到[与其他节点的最大距离]最小的节点
            if min_max_delay<= self.delay_limit:
                self.core_node = dict_max_delay[min_max_delay]
                self.max_delay = min_max_delay
            else:
                print('Error：when choose core node---->最大时延超过约束条件')
                raise Exception
        elif len(self.this_group) == 1:
            self.core_node = self.this_group[0]
            self.max_delay = self.__get_delay(self.core_node, self.core_node)

        # debug---->查找max_delay仍然为None的原因
        if self.max_delay is None:
            print('choose core node出错---->self.max_delay 为 None')
            raise Exception('error')



    def pk_value(self):
        """
        返回 pk value用于两个group兼并
        :return:
        """
        if len(self.this_group) ==1:
            return 0  # 单独构成的grouppk值最低，优先选择被兼并
        else:
            # *******************************
            # 旧 pk方法
            # return self.total_workload/self.max_delay
            
            # 只考虑时延
            return -self.max_delay

    def can_absorb(self, item):
        if self.__get_delay(self.core_node, item) <= self.delay_limit and item.workload + self.total_workload <= self.workload_limit:
            return True
        else:
            return False

    def get_core_node(self):
        """
        :return: core node 的 id
        """
        return self.core_node

    # 获取指标
    def get_max_delay(self):
        """
        :return: 返回核心指标
        """
        return self.max_delay

    def get_total_workload(self) -> float:
        """
        :return: 返回
        """
        return self.total_workload

    def __get_delay(self, a, b):
        if isinstance(a, EdgeServer) and isinstance(b, EdgeServer):
            return self.topology[a.base_station_id][b.base_station_id]
        elif isinstance(a, BaseStation) and isinstance(b, BaseStation):
            return self.topology[a.id][b.id]
        else:
            print('计算了部署edge或base station的时延')
            raise Exception

    # ==========================================================================


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    start_time = "start run at: {0}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # 载入edge信息
    # 格式：list每个元素是edge_server类
    with open(config.edge_info_name, 'rb') as f:
        edge_list = pickle.load(f)

    data = DataUtils('../data/基站经纬度_修改完整版_增加缺失地址_修改重复地址.csv', '../data/上网信息输出表（日表）7月15号之后.csv')
    topology = generate_topology(data)

    # =====================================
    eu = []  # edge_unattached
    for i in range(5):
        e = EdgeServer(i, 0, 0, i)
        eu.append(e)

    g1 = GreedyGroup(topology, eu, eu[0], eu[1])
    print('after g1---->', eu, '\ng1---->', g1)
    g2 = GreedyGroup(topology, eu, eu[1], eu[0])
    print('after g2---->', eu)
    g3 = GreedyGroup(topology, eu, eu[0])
    print('after g3---->', eu)

    gg2=g2.dissolve()
    print('after gg2---->', eu)

    g1.insert(gg2)

    print('after incert eu---->', eu)
    print('after incert g1---->', g1.this_group)

    print('g1.corenode---->\n', g1.get_core_node())
    print('g1.maxdelay', g1.get_max_delay())
    print('g1.total_load', g1.get_total_workload())
    print('g1.this_group', [i.id for i in g1.this_group])


    # =====================================

    end_time = "end run at:{0}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    print('\n\n\n')
    logging.info(start_time)
    logging.info(end_time)