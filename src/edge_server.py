class EdgeServer(object):
    # 考虑加入workload的上限
    max_workload = 3000000

    def __init__(self, id, latitude, longitude, base_station_id=None):
        self.id = id
        self.latitude = latitude
        self.longitude = longitude
        self.base_station_id = base_station_id
        self.assigned_base_stations = []
        self.workload = 0

    def __str__(self):
        return 'edge_info'.center(30, '=') + '\n EDGE ID \t----> {0}\n Location \t----> {1}\n BS_No \t\t----> {2}\n BS_list \t----> {3}\n Workload \t----> {4}'.format(
            self.id, (self.latitude, self.longitude), self.base_station_id, [i.id for i in self.assigned_base_stations],
            self.workload)
