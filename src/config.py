

'''
本文件用于记录全局的配置变量
'''



# ===========================edge placement===========================================
# edge_coverage = (2, 8)  # (2, 11)  km
edge_coverage_record = 5  # 实际部署用的距离，用于后续的服务部署
edge_placement_max_generation =  10 # 400  
# force_update_rate = 0.2
# =======================workload dispatching============================================

# edge_info_name = '../cache/edge_info_l' + str(max_link) + '_d' + str(max_dis)
edge_info_name = '../cache/edge_info_'+str(edge_coverage_record)

'''
适用参数组合
max_link      max_dis     coverage        price
15              10          10             180
20              10          10             150 
'''
# =====================================
# 选择topology参数
max_link = 15  # 初始化topology时，单个节点允许链接多少个相邻节点
max_dis = 10   # 可以接入的节点最远距离,单位km
# =====================================

pso_repeat = 2

# ============sla相关参数===============
electircity_price = 0.925
config_max_payment= 0.0016 # 0.005 # 0.0016  # 每分钟单价
delay_ratio = 0.5  # ideal_delay/maad

# 是否使用Q-PSO
# qpso = False # True















srv_print_log = False
# service实验
# pso最大迭代次数
pso_max_iteration = 400
# PSO求平均次数
PSO_average_times = 5
greedy_average_times = 5
# 默认参数，用于set parameter
srv_coverage = 8
srv_price = 1000  # 180
srv_max_load = 30000000
srv_max_balance = 25000000

# 全局设置,实验的测试范围
# global_coverage = (4, 15)  # (4, 15)
# global_price = (100, 600, 20)
# global_loadbalance = (10000000, 50000000, 2000000)
# global_workload = range(10000000, 80000000, 5000000)

# global_coverage = (0, 0)  # (4, 15)
global_price = (0, 0)  # (100, 600, 20)
global_loadbalance = (0, 0)  # (10000000, 50000000, 2000000)
global_workload = [3000000*20/i for i in range(2, 21)]
# Random方法求平均次数
cal_average_num = 10
