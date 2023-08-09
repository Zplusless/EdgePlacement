class BaseStation:
    """基站
    
    Attributes:
        id: 编号
        address: 名称 地址
        latitude: 纬度
        longitude: 经度
        user_num: 用户数量
        workload: 总使用时间 单位分钟
    """

    def __init__(self, id, addr, lat, lng):
        self.id = id    # 经过util类处理后，bs的id同它在base_stations中的位置
        self.address = addr
        self.latitude = lat
        self.longitude = lng
        self.user_num = 0
        self.workload = 0

    def __str__(self):
        return '='*45+"\nBS_{0}: {1}---->{2}\nuser_num:{3}\nworkload:{4}".format(self.id, self.address, (self.latitude, self.longitude), self.user_num, self.workload)
