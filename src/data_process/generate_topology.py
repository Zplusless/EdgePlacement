'''
利用数据集，生成基站的连接关系

将孤岛状的基站，做出拓扑结构


项目的working directory设置为src文件夹
'''
import sys
sys.path.append("..")

# import config
from config import *
from utils import *
import heapq
import typing
from openpyxl import Workbook
import csv

import os
import re
from pprint import pprint
import random


# 运用topology计算距离，直接用bs的id带入矩阵下标即可
@memorize('../cache/topology_l'+str(max_link)+'_d'+str(max_dis))
def generate_topology(data):

    # ================初始化=====================
    total_num = len(data.distances)
    topology = [[9999 for i in range(total_num)]for j in range(total_num)]
    for i in range(total_num):
        # 研究第i行，也就是第i个基站
        dis_list_i = data.distances[i].copy()
        a = data.base_stations[i]  # 标记第i个自身

        # distances矩阵中，自身和其它因为数据错误导致的0不考虑
        for j in range(len(dis_list_i)):
            if dis_list_i[j] == 0:
                b = data.base_stations[j]
                dis = DataUtils.calc_distance(a.latitude, a.longitude, b.latitude, b.longitude)
                dis_list_i[j] = dis if dis > 0 else 9999

        # 求出最近的max_link个的id
        min_num_index_list = list(map(dis_list_i.index, heapq.nsmallest(max_link, dis_list_i)))

        # print(min_num_index_list, end='       ')
        # d = [dis_list_i[k] for k in min_num_index_list]
        # print(d)

        for min_index in min_num_index_list:
            # 几个最近的基站中，小于max_dis的标1表示一跳距离
            if dis_list_i[min_index] < max_dis:
                topology[i][min_index] = 1

    # 保证矩阵对称，图是双向图
    for row in range(total_num):
        for col in range(row, total_num):  # 只遍历上半矩阵
            # if topology[row][col] == 1:
            #     topology[col][row] == 1
            topology[col][row] = topology[row][col]
    # debug
    # for line in topology:
    #     print(line.count(1)+line.count(9999))

    # ================利用弗洛伊德计算最短路径=====================
    floyd(topology)

    # 返回生成的topology
    return topology


# 弗洛伊德计算最短距离
def floyd(topology: List[List[int]]):
    total_num = len(topology)
    for k in range(total_num):
        print('\r' + str(k) + '[' + '#'*int(k/total_num*50) + ' '*(50-int(k/total_num*50)) + ']', end='', flush=True)
        for i in range(total_num):  # 行
            for j in range(total_num):  # 列
                if i == j:
                    topology[i][j] = 0
                elif topology[i][j] > topology[i][k]+topology[k][j]:
                    topology[i][j] = topology[i][k] + topology[k][j]


class UPF_path:
    def __init__(self, topology, min_dis, max_num, delay_list=None):
        """
        生成考虑UPF情况下的拓扑

        Args:
            topology (List[List]): 拓扑矩阵，每个数字表示跳数
            min_dis (int): 相邻upf最小跳数
            max_num (int): 最多部署多少个upf
            delay_list (Linst[float], optional): 利用mini5Gedge生成的跳数到delay的映射表格. Defaults to None.
        """
        self.topology = topology
        self.pre_hop_set = set()
        self.next_hop_set = set()

        self.min_dis = min_dis
        self.max_num = max_num

        self.upfs = self.choose_upf(topology, min_dis, max_num)
        self.nearest_upf = self.get_nearest_upf()
        self.upf_path_matrix = self.get_upf_path_matrix()
        self.delay_list = delay_list

        # 去除不可达点的跳数
        self.pre_hop_set.remove(9999)
        self.next_hop_set.remove(9999)

        self.delay_matrix = self.get_delay_matrix()

        
    # 选择upf
    def choose_upf(self, topology, min_dis, max_num):
        """
        choose upf
        因为是基于跳数选择upf，所以不用担心UPF全局平均部署带来的
        基站密集的地方upf相对稀疏

        Args:
            topology (List): 距离矩阵
            min_dis (int): 两个upf间最大距离
            max_num (int): 最多允许多少个upf
        """
        upf_bs_list = []
        bs_num = len(topology)
        iter_start = 200
        p = iter_start + 1
        while(p != iter_start):
            if upf_bs_list:
                temp_dis = [topology[i][p] for i in upf_bs_list]
                if min(temp_dis) > min_dis:
                    upf_bs_list.append(p)
            else:
                upf_bs_list.append(p)

            p = (p+1)%bs_num
        

        while len(upf_bs_list) > max_num:
            min_upf_dis = 999
            to_del = None
            # upf_dis_del = [999 for i in range(len(upf_bs_list) - max_num)]
            for i in range(len(upf_bs_list) -1 ):
                for j in range(i, len(upf_bs_list)):
                    x = upf_bs_list[i]
                    y = upf_bs_list[j]
                    dis = topology[x][y]

                    if dis < min_upf_dis:
                        min_upf_dis = dis
                        to_del = x
            
            upf_bs_list.remove(to_del)
        return upf_bs_list

    def get_nearest_upf(self):
        nearest_upf = {}
        for i in range(len(self.topology)):
            temp = 9999
            nearest = None
            for u in self.upfs:
                if self.topology[i][u] < temp:
                    nearest = u
                    temp = self.topology[i][u]
            nearest_upf[i] = nearest, temp
        return nearest_upf

    def get_upf_path_matrix(self):
        bs_num = len(self.topology)
        path = [[None for i in range(bs_num)] for j in range(bs_num)]
        for i in range(bs_num):
            for j in range(i, bs_num):
                temp_dis = 99999
                temp_u = None
                for u in self.upfs:
                    dis = self.topology[i][u] + self.topology[u][j]
                    if dis < temp_dis:
                        temp_dis = dis
                        temp_u = u
                
                # 记录upf前置跳数和后置跳数
                self.pre_hop_set.add(self.topology[i][temp_u])
                self.next_hop_set.add(self.topology[temp_u][j])

                # 记录路径选择的upf
                path[i][j] = temp_u
                path[j][i] = temp_u
        return path

    def get_upf_path(self, start, end):
        """
        return upf in the path and the hops

        Args:
            start (int): start bs
            end (int): end bs

        Returns:
            tuple: upf, hops between start bs and upf, hops between upf and end bs
        """
        upf = self.upf_path_matrix[start][end]
        pre_hops = self.topology[start][upf]
        next_hops = self.topology[upf][end]
        return upf, pre_hops, next_hops


    def get_delay(self, start, end):
        upf, pre_hops, next_hops = self.get_upf_path(start, end)
        
        if self.delay_list:
            # 需要考虑两个节点不可达的情况
            pre_delay = 9999 if pre_hops==9999 else self.delay_list['pre'][pre_hops]
            next_delay = 9999 if next_hops==9999 else self.delay_list['next'][next_hops]
        else:

            pre_delay = pre_hops + random.random()
            next_delay = next_hops + random.random()

        return pre_delay, next_delay

    
    # def get_delay_matrix(self):
    #     @memorize(f'../cache/upf_delay_matrix[{self.min_dis},{self.max_num}]')
    #     def calculate():
    #         ans = [[sum(self.get_delay(i,j)) for j in range(len(self.topology))] for i in range(len(self.topology))]
    #         return ans
    #     return calculate
    
    def get_delay_matrix(self):

        ans = [[sum(self.get_delay(i,j)) for j in range(len(self.topology))] for i in range(len(self.topology))]
        return ans

class DelayProcess:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.all_data = self.get_all_data()
    
    def process_file(self, file):
        ans = []
        temp = None
        with open(file, 'r') as f:
            temp = f.readlines()
            # print(temp[3:])
        for line in temp[3:]:
            target = re.search('time=(.*) ms', line)#.group(1)
            if target:
                delay = float(target.group(1))
                ans.append(delay)
        return ans

    def get_all_data(self):
        dir_list = os.listdir(self.root_dir)
        all_data = {'pre':{}, 'next':{}, 'all':{}}

        cwd = os.getcwd()

        for d in dir_list:
            # d = os.path.join(self.root_dir, d)
            if os.path.isdir(os.path.join(self.root_dir, d)):
                pre, next = map(int, d.split('_'))
                all_data['pre'][(pre, next)] = self.process_file(os.path.join(self.root_dir, d, 'ran2iupf.txt'))
                all_data['next'][(pre, next)] = self.process_file(os.path.join(self.root_dir, d, 'aupf2dn.txt'))
                all_data['all'][(pre, next)] = self.process_file(os.path.join(self.root_dir, d, 'ue2dn.txt'))
        return all_data

    def get_ave_delay(self):
        ave_delay = {'pre':{}, 'next':{}, 'all':{}}
        for k in self.all_data['pre'].keys():
            ave_delay['pre'][k[0]] = sum(self.all_data['pre'][k])/len(self.all_data['pre'][k])
            ave_delay['next'][k[1]] = sum(self.all_data['next'][k])/len(self.all_data['next'][k])
            # ave_delay['all'][k] = sum(self.all_data['all'][k])/len(self.all_data['all'][k])
        return ave_delay


if __name__ == '__main__':

    print(os.getcwd())

    os.chdir(r'F:\博士学习\1.论文写作\TMC_edge_deployment\实验\experiment\srv_development_TMC\src')
    # os.chdir(r'/home/test/code/src')

    data = DataUtils(r'../data/基站经纬度_修改完整版_增加缺失地址_修改重复地址.csv', r'../data/上网信息输出表（日表）7月15号之后.csv')
    print(len(data.distances), len(data.distances[0]))

    # wb = Workbook()
    # ws = wb.active
    # ws.append(['max', 'len'])

    topology = generate_topology(data)
    # for debug
    # print(topology[492][262])

    # print_matrix(topology)

    # pprint(topology)

    delay_data = DelayProcess(r'../data/measure0.2')
    ave_delay = delay_data.get_ave_delay()

    upath = UPF_path(topology, 3, 100, ave_delay)
    print(upath.get_upf_path(0,10))
    print('pre_hops:', upath.pre_hop_set)
    print('next_hops:', upath.next_hop_set)


    pprint(upath.delay_matrix[16][16])

    # upfs = get_choose_upf(topology, 3, 1000)
    # pprint(upfs)
    # # print(len(upfs))

    # nearest_upfs = nearest_upf(topology, upfs)
    # # print(-1 in nearest_upfs)
    # pprint(nearest_upfs)


    # dis_dict = {}
    # for i in range(len(topology)):
    #     l = []
    #     for dis in topology[i]:
    #         if dis < 9999:
    #             l.append(dis)
    #     # print(topology[i].count(9999), '    ', max(topology[i]))
    #     # print(max(l),'   ',len(l))
    #     ws.append([max(l), len(l)])
    #     if i == 6:
    #         for dd in range(max(l)):
    #             dis_dict[dd] = l.count(dd)
    # wb.save(r'C:\Users\MonsterZ\Desktop\topology\topology_l'+str(max_link)+'_d'+str(max_dis)+'.xlsx')
    #
    # print(dis_dict)
    # with open(r'C:\Users\MonsterZ\Desktop\topology\topology_l'+str(max_link)+'_d'+str(max_dis)+'.txt', 'w') as fff:
    #     print(dis_dict, file=fff)
    #
    # with open(r'C:\Users\MonsterZ\Desktop\topology\拓扑实图_l'+str(max_link)+'_d'+str(max_dis)+'.csv', 'w', newline='') as ff_csv:
    #     topology_csv_writer = csv.writer(ff_csv)
    #     topology_csv_writer.writerows(topology)
