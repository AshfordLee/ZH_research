from datetime import datetime, timedelta
import csv
import random
import argparse
import sys
import os

class MovingAverage:
    def __init__(self, num_bin: int, window: float):
        """
        初始化移动平均计算类
        
        参数:
        - num_bin: 用于存储的内存大小
        - window: 回溯窗口大小（秒）
        """
        self.num_bin = num_bin  # 存储桶的数量
        self.window = window    # 窗口大小（秒）
        self.data = []          # 存储(timestamp, value)对的列表
        self.current_timestamp = None
        
        # 交易时间设置
        self.trading_hours = {
            'morning_start': '09:30:00',
            'morning_end': '11:30:00',
            'afternoon_start': '13:00:00',
            'afternoon_end': '15:00:00'
        }
        
        # 用于记录日志的CSV文件
        self.log_file = None
        self.csv_writer = None
    
    def set_log_file(self, filename):
        """设置日志文件"""
        self.log_file = open(filename, 'w', newline='')
        fieldnames = ['索引', '时间戳', '日期时间', '与当前时间的差距(秒)', '交易时段', '是否为交易时间', '价格', 'SMA', '点类型', '跨日/跨时段']
        self.csv_writer = csv.DictWriter(self.log_file, fieldnames=fieldnames)
        self.csv_writer.writeheader()
    
    def is_trading_time(self, timestamp):
        """检查给定时间戳是否在交易时间内"""
        dt = datetime.fromtimestamp(timestamp)
        date_str = dt.strftime('%Y-%m-%d')
        
        # 检查是否是周末
        if dt.weekday() >= 5:  # 5是周六，6是周日
            return False
            
        # 检查是否在交易时段内
        morning_start = datetime.strptime(f"{date_str} {self.trading_hours['morning_start']}", "%Y-%m-%d %H:%M:%S")
        morning_end = datetime.strptime(f"{date_str} {self.trading_hours['morning_end']}", "%Y-%m-%d %H:%M:%S")
        afternoon_start = datetime.strptime(f"{date_str} {self.trading_hours['afternoon_start']}", "%Y-%m-%d %H:%M:%S")
        afternoon_end = datetime.strptime(f"{date_str} {self.trading_hours['afternoon_end']}", "%Y-%m-%d %H:%M:%S")
        
        return (morning_start <= dt <= morning_end) or (afternoon_start <= dt <= afternoon_end)
    
    def Update(self, timestamp: float, value: float):
        """
        新数据到达，更新状态
        
        参数:
        - timestamp: (float) 时间戳
        - value: (float) 股票价格
        """
        # 更新当前时间戳
        self.current_timestamp = timestamp
        
        # 添加新数据
        self.data.append((timestamp, value))
        
        # 如果数据量超过num_bin，需要进行取舍
        if len(self.data) > self.num_bin:
            # 采用不等距采样策略：近期数据保留更多，早期数据保留更少
            data_length = len(self.data)
            
            # 对数据进行时间排序
            sorted_data = sorted(self.data, key=lambda x: x[0])
            
            # 将数据分为三个部分：早期(20%)、中期(30%)、近期(50%)
            early_end = int(data_length * 0.2)
            mid_end = int(data_length * 0.5)
            
            # 计算每部分应保留的数据点数量
            early_keep = max(1, int(self.num_bin * 0.1))  # 早期保留10%
            mid_keep = max(1, int(self.num_bin * 0.3))    # 中期保留30%
            recent_keep = self.num_bin - early_keep - mid_keep  # 近期保留60%
            
            # 对各部分进行采样
            # 早期数据采样（稀疏）
            early_data = sorted_data[:early_end]
            if early_data:
                early_indices = [i * len(early_data) // early_keep for i in range(early_keep)]
                early_sampled = [early_data[i] for i in early_indices]
            else:
                early_sampled = []
            
            # 中期数据采样（中等密度）
            mid_data = sorted_data[early_end:mid_end]
            if mid_data:
                mid_indices = [i * len(mid_data) // mid_keep for i in range(mid_keep)]
                mid_sampled = [mid_data[i] for i in mid_indices]
            else:
                mid_sampled = []
            
            # 近期数据采样（密集）
            recent_data = sorted_data[mid_end:]
            if recent_data:
                recent_indices = [i * len(recent_data) // recent_keep for i in range(recent_keep)]
                recent_sampled = [recent_data[i] for i in recent_indices]
            else:
                recent_sampled = []
            
            # 组合采样结果
            self.data = early_sampled + mid_sampled + recent_sampled
            
            # 确保最新的数据点一定被保留
            if sorted_data and sorted_data[-1] not in self.data:
                # 替换倒数第二个点为最新点
                self.data[-1] = sorted_data[-1]
    
    def Get(self) -> float:
        """
        计算并返回当前回溯窗口的SMA值
        
        返回:
        - float: 当前回溯窗口的SMA (简单移动平均)值
        """
        return self.GetSMA()
    
    def GetSMA(self) -> float:
        """
        计算当前回溯窗口的简单移动平均线(SMA)
        使用O(1)的空间复杂度实现
        
        返回:
        - float: SMA值
        """
        if not self.current_timestamp:
            return 0.0
        
        # 回溯窗口的起始时间
        window_start = self.current_timestamp - self.window
        
        # 用于累计SMA计算的变量
        total_price = 0.0
        valid_points_count = 0
        
        # 当前正在检查的时间点，从当前时间开始往回推
        check_time = self.current_timestamp
        
        # 获取当前价格，如果data为空则使用默认价格100.0
        current_price = self.data[-1][1] if self.data else 100.0
        
        # 获取原始数据点的时间戳(仅用于日志)
        original_timestamps = [ts for ts, _ in self.data]
        
        # 记录不同交易时段和日期的数据点(仅用于日志)
        current_dt = datetime.fromtimestamp(self.current_timestamp)
        current_date = current_dt.date()
        current_session = "morning" if current_dt.hour < 12 else "afternoon"
        
        # 记录发现的时段和日期(仅用于日志)
        found_sessions = {current_session}
        found_dates = {current_date}
        
        # 记录跨时段和跨日标志(仅用于日志)
        is_cross_session = False
        is_cross_day = False
        
        # 记录窗口内的时间戳(仅用于CSV日志)
        timestamps_for_log = []
        
        # 检查是否在下午交易时段，如果是，需要特殊处理
        is_afternoon_session = current_session == "afternoon"
        
        # 如果当前时间点是下午交易时段开始后不久的时间（例如，下午开盘后300秒内）
        # 需要确保回溯能够正确处理跨时段情况
        if is_afternoon_session:
            afternoon_start = datetime.strptime(f"{current_date.strftime('%Y-%m-%d')} {self.trading_hours['afternoon_start']}", "%Y-%m-%d %H:%M:%S")
            # 计算当前时间与下午开盘时间的差值（秒）
            seconds_since_afternoon_open = (current_dt - afternoon_start).total_seconds()
            
            # 如果当前时间是下午开盘后且回溯窗口超过了下午已交易的时间
            # 需要确保能够回溯到上午交易时段
            if seconds_since_afternoon_open < self.window:
                # 标记为跨时段
                is_cross_session = True
                found_sessions.add("morning")
        
        # 回溯到窗口起始时间
        while check_time >= window_start and check_time >= 0:
            # 只有在交易时间内的点才计入窗口
            if self.is_trading_time(check_time):
                # 检查当前时间点的日期和时段
                check_dt = datetime.fromtimestamp(check_time)
                check_date = check_dt.date()
                check_session = "morning" if check_dt.hour < 12 else "afternoon"
                
                # 更新发现的时段和日期集合
                found_sessions.add(check_session)
                found_dates.add(check_date)
                
                # 更新跨时段和跨日标志
                is_cross_session = len(found_sessions) > 1
                is_cross_day = len(found_dates) > 1
                
                # 为当前检查的时间点找到一个价格
                price_at_time = self._find_price_at_time(check_time, current_price)
                
                # 如果价格大于0，累加到总价中用于计算SMA
                if price_at_time > 0:
                    total_price += price_at_time
                    valid_points_count += 1
                
                # 记录时间戳用于日志(仅用于CSV日志)
                if self.csv_writer:
                    timestamps_for_log.append(check_time)
            
            # 向前移动1秒
            check_time -= 1
            
            # 如果进入了非交易时间，需要跳过到前一个交易时段的结束时间
            if not self.is_trading_time(check_time) and check_time > 0:
                check_dt = datetime.fromtimestamp(check_time)
                check_date = check_dt.strftime('%Y-%m-%d')
                check_hour = check_dt.hour
                check_minute = check_dt.minute
                
                # 找到要跳转到的时间点
                jump_to_time = None
                
                # 如果在中午休市时间
                if 11 <= check_hour < 13:
                    # 跳转到上午收盘时间
                    morning_end = datetime.strptime(f"{check_date} {self.trading_hours['morning_end']}", "%Y-%m-%d %H:%M:%S")
                    jump_to_time = morning_end.timestamp()
                    
                    # 更新时段信息
                    found_sessions.add("morning")
                    is_cross_session = True
                # 如果在凌晨或夜间（跨日）
                elif check_hour < 9 or check_hour >= 15:
                    # 找到前一交易日
                    check_day = datetime.strptime(check_date, "%Y-%m-%d").date()
                    prev_day = check_day - timedelta(days=1)
                    
                    # 跳过周末
                    while prev_day.weekday() >= 5:  # 5是周六，6是周日
                        prev_day -= timedelta(days=1)
                    
                    # 跳转到前一交易日的收盘时间
                    prev_date_str = prev_day.strftime('%Y-%m-%d')
                    afternoon_end = datetime.strptime(f"{prev_date_str} {self.trading_hours['afternoon_end']}", "%Y-%m-%d %H:%M:%S")
                    jump_to_time = afternoon_end.timestamp()
                    
                    # 更新日期和时段信息
                    found_dates.add(prev_day)
                    found_sessions.add("afternoon")
                    is_cross_day = True
                    is_cross_session = True
                
                # 执行跳转
                if jump_to_time is not None and jump_to_time < check_time:
                    check_time = jump_to_time
        
        # 特殊处理下午开盘后回溯的情况
        # 如果当前是下午交易时段，且回溯窗口尚未完成，需要继续回溯至上午收盘
        if is_afternoon_session and valid_points_count < self.window:
            # 找到当天上午收盘时间
            morning_end = datetime.strptime(f"{current_date.strftime('%Y-%m-%d')} {self.trading_hours['morning_end']}", "%Y-%m-%d %H:%M:%S")
            morning_end_ts = morning_end.timestamp()
            
            # 从上午收盘时间开始继续回溯
            check_time = morning_end_ts
            
            # 更新时段信息
            found_sessions.add("morning")
            is_cross_session = True
            
            # 计算还需要回溯的交易秒数
            remaining_seconds = self.window - valid_points_count
            
            # 继续回溯收集上午时段的数据
            while check_time >= 0 and remaining_seconds > 0:
                if self.is_trading_time(check_time):
                    # 为上午时段的时间点找到价格
                    price_at_morning = self._find_price_at_time(check_time, current_price)
                    
                    # 如果价格大于0，累加到总价中用于计算SMA
                    if price_at_morning > 0:
                        total_price += price_at_morning
                        valid_points_count += 1
                    
                    # 记录时间戳用于日志(仅用于CSV日志)
                    if self.csv_writer:
                        timestamps_for_log.append(check_time)
                        
                    remaining_seconds -= 1
                
                # 向前移动1秒
                check_time -= 1
                
                # 如果离开交易时间，需要处理跳转
                if not self.is_trading_time(check_time) and check_time > 0:
                    check_dt = datetime.fromtimestamp(check_time)
                    check_date = check_dt.strftime('%Y-%m-%d')
                    check_hour = check_dt.hour
                    
                    # 如果到达非交易时间，需要跳转
                    jump_to_time = None
                    
                    # 如果到达前一天，跳转到前一交易日收盘
                    if check_hour < 9 or check_hour >= 15:
                        # 找到前一交易日
                        check_day = datetime.strptime(check_date, "%Y-%m-%d").date()
                        prev_day = check_day - timedelta(days=1)
                        
                        # 跳过周末
                        while prev_day.weekday() >= 5:
                            prev_day -= timedelta(days=1)
                        
                        # 跳转到前一交易日的收盘时间
                        prev_date_str = prev_day.strftime('%Y-%m-%d')
                        afternoon_end = datetime.strptime(f"{prev_date_str} {self.trading_hours['afternoon_end']}", "%Y-%m-%d %H:%M:%S")
                        jump_to_time = afternoon_end.timestamp()
                        
                        # 更新标志
                        found_dates.add(prev_day)
                        found_sessions.add("afternoon")
                        is_cross_day = True
                        is_cross_session = True
                    
                    # 执行跳转
                    if jump_to_time is not None and jump_to_time < check_time:
                        check_time = jump_to_time
        
        # 计算SMA
        sma = total_price / valid_points_count if valid_points_count > 0 else 0.0
        
        # 记录到CSV (仅当需要时)
        if self.csv_writer and timestamps_for_log:
            # 构建所需的窗口数据格式用于日志记录
            window_data_for_log = []
            for ts in timestamps_for_log:
                price = self._find_price_at_time(ts, current_price)
                is_original = abs(ts - min(original_timestamps, key=lambda x: abs(x - ts))) < 0.1 if original_timestamps else False
                window_data_for_log.append((ts, price, is_original))
            self.log_to_csv(window_data_for_log, sma)
        
        return sma
    
    # def calculate_sma(self, data_points):
    #     """
    #     计算简单移动平均线(SMA)
    #     只考虑原始数据点，且忽略价格为0的数据点（这些点代表已越过数据开始日期）
        
    #     参数:
    #     - data_points: 包含(timestamp, price)元组的列表，仅包含原始数据点
        
    #     返回:
    #     - SMA值
    #     """
    #     if not data_points:
    #         return 0.0
        
    #     # 过滤掉价格为0的数据点
    #     valid_data_points = [(ts, price) for ts, price in data_points if price > 0]
        
    #     if not valid_data_points:
    #         return 0.0
        
    #     # 计算所有非零价格的算术平均值
    #     total_price = sum(price for _, price in valid_data_points)
    #     count = len(valid_data_points)
        
    #     if count == 0:
    #         return 0.0
            
    #     return total_price / count
    
    def _find_price_at_time(self, timestamp, default_price=100.0):
        """
        找到指定时间戳对应的价格
        如果找不到精确匹配，则使用最近的价格或默认价格
        核心原则：两条数据之间的所有时间点上，价格都等于第一条数据的价格
        边界条件：如果回溯窗口内的点比最早的数据点还早，价格为0
        """
        if not self.data:
            return default_price
        
        # 先查找精确匹配
        for ts, price in self.data:
            if abs(ts - timestamp) < 0.1:  # 允许0.1秒的误差
                return price
        
        # 找不到精确匹配，查找前一个时间点
        # 寻找最近的但时间小于当前时间点的数据
        prev_ts = None
        prev_price = None
        
        # 获取所有数据点并按时间排序
        sorted_data = sorted(self.data)
        
        # 如果当前时间点比最早的数据点还早，返回0
        if sorted_data and timestamp < sorted_data[0][0]:
            return 0.0
        
        for ts, price in sorted_data:
            if ts > timestamp:
                # 如果已经超过当前时间点，结束查找
                break
            # 更新前一个时间点和价格
            prev_ts = ts
            prev_price = price
        
        # 如果找到了前一个时间点，使用该价格
        if prev_ts is not None:
            return prev_price
        
        # 如果没有找到前一个时间点，说明当前时间点比所有数据都早
        # 根据边界条件，返回0
        return 0.0
    
    def log_to_csv(self, timestamps_with_prices, sma=0.0):
        """将时间戳、价格和SMA记录到CSV文件"""
        if not self.csv_writer:
            return
            
        # 获取当前时间对象
        current_dt = datetime.fromtimestamp(self.current_timestamp)
        current_date = current_dt.date()
        
        # 获取所有时间戳的日期，用于检测跨日情况
        dates_in_window = set()
        for ts, _, _ in timestamps_with_prices:
            dates_in_window.add(datetime.fromtimestamp(ts).date())
        is_cross_day = len(dates_in_window) > 1
        
        # 检测是否跨时段（上午/下午）
        morning_timestamps = 0
        afternoon_timestamps = 0
        for ts, _, _ in timestamps_with_prices:
            dt = datetime.fromtimestamp(ts)
            if dt.hour < 12:
                morning_timestamps += 1
            else:
                afternoon_timestamps += 1
        is_cross_session = morning_timestamps > 0 and afternoon_timestamps > 0
        
        # 写入每个时间点的数据
        for i, (ts, price, is_original) in enumerate(timestamps_with_prices):
            dt = datetime.fromtimestamp(ts)
            time_diff = self.current_timestamp - ts  # 与当前时间的差距（秒）
            session = "上午" if dt.hour < 12 else "下午"
            is_trading = "是" if self.is_trading_time(ts) else "否"
            
            # 所有有效数据点都显示相同的SMA值（无论是原始还是补充点）
            display_sma = sma if price > 0 else 0.0
            
            # 添加是否为原始数据点的标记
            point_type = "原始数据点" if is_original else "补充点"
            
            # 添加跨日和跨时段标记
            cross_info = []
            if is_cross_day and dt.date() != current_date:
                cross_info.append("跨日")
            if is_cross_session and ((session == "上午" and afternoon_timestamps > 0) or (session == "下午" and morning_timestamps > 0)):
                cross_info.append("跨时段")
            cross_status = "、".join(cross_info) if cross_info else "同日同时段"
            
            self.csv_writer.writerow({
                '索引': i+1,
                '时间戳': ts,
                '日期时间': dt.strftime('%Y-%m-%d %H:%M:%S'),
                '与当前时间的差距(秒)': round(time_diff, 1),
                '交易时段': session,
                '是否为交易时间': is_trading,
                '价格': round(price, 2),
                'SMA': round(display_sma, 2),
                '点类型': point_type,
                '跨日/跨时段': cross_status
            })
        
        self.log_file.flush()  # 确保数据写入文件
    
    def close_log_file(self):
        """关闭日志文件"""
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None

def get_user_input():
    """
    获取用户输入的参数
    
    返回:
    - num_bin: 桶的数量
    - window: 时间窗口大小（秒）
    - start_timestamp: 起始时间戳
    - num_points: 生成的数据点数量
    - output_file: 输出文件路径
    """
    print("===== 移动平均和回溯窗口测试程序 =====")
    
    # 获取桶数量
    while True:
        try:
            num_bin = int(input("请输入桶的数量 (默认为10): ") or "10")
            if num_bin > 0:
                break
            else:
                print("桶的数量必须大于0")
        except ValueError:
            print("请输入有效的数字")
    
    # 获取时间窗口大小
    while True:
        try:
            window = int(input("请输入时间窗口大小(秒) (默认为1000): ") or "1000")
            if window > 0:
                break
            else:
                print("时间窗口必须大于0")
        except ValueError:
            print("请输入有效的数字")
    
    # 获取起始时间戳
    while True:
        try:
            date_str = input("请输入起始日期 (YYYY-MM-DD) (默认为2025-04-04): ") or "2025-04-04"
            time_str = input("请输入起始时间 (HH:MM:SS) (默认为09:30:00): ") or "09:30:00"
            
            # 验证日期和时间格式
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            
            # 检查是否为交易日（周一至周五）
            if start_dt.weekday() >= 5:  # 5是周六，6是周日
                print(f"错误：{date_str}是周末，不是交易日。请输入周一至周五的日期。")
                continue
                
            start_timestamp = start_dt.timestamp()
            
            print(f"起始时间设置为: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            break
        except ValueError as e:
            print(f"无效的日期或时间格式: {e}")
    
    # 获取数据点数量
    while True:
        try:
            num_points = int(input("请输入要生成的数据点数量 (默认为20): ") or "20")
            if num_points > 0:
                break
            else:
                print("数据点数量必须大于0")
        except ValueError:
            print("请输入有效的数字")
    
    # 获取输出文件路径
    output_file = input("请输入输出文件路径 (默认为output.csv): ") or "output.csv"
    
    return num_bin, window, start_timestamp, num_points, output_file

def generate_test_data(start_timestamp, num_points):
    """
    生成测试数据
    
    参数:
    - start_timestamp: 起始时间戳
    - num_points: 生成的数据点数量
    
    返回:
    - 生成的数据点列表，每个元素为 (timestamp, price) 元组
    """
    # 使用固定的随机种子以获得可重复的结果
    random.seed(42)
    
    # 如果给定的起始时间戳不是交易时间，则调整到下一个交易时间
    ma = MovingAverage(10, 60)
    if not ma.is_trading_time(start_timestamp):
        current_dt = datetime.fromtimestamp(start_timestamp)
        current_date = current_dt.date()
        
        # 如果当前时间在上午交易时段前，则调整到当天上午开盘时间
        if current_dt.hour < 9 or (current_dt.hour == 9 and current_dt.minute < 30):
            next_trading_time = datetime.strptime(f"{current_date.strftime('%Y-%m-%d')} 09:30:00", "%Y-%m-%d %H:%M:%S")
        # 如果当前时间在上午交易时段结束后，下午交易时段前，则调整到当天下午开盘时间
        elif (current_dt.hour == 11 and current_dt.minute >= 30) or (current_dt.hour == 12):
            next_trading_time = datetime.strptime(f"{current_date.strftime('%Y-%m-%d')} 13:00:00", "%Y-%m-%d %H:%M:%S")
        # 如果当前时间在当天交易时段结束后，则调整到下一个交易日的上午开盘时间
        else:
            next_day = current_date + timedelta(days=1)
            # 如果下一天是周末，则调整到下周一
            while next_day.weekday() >= 5:  # 5是周六，6是周日
                next_day += timedelta(days=1)
            next_trading_time = datetime.strptime(f"{next_day.strftime('%Y-%m-%d')} 09:30:00", "%Y-%m-%d %H:%M:%S")
        
        start_timestamp = next_trading_time.timestamp()
        print(f"已调整起始时间为: {datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    
    data = []
    
    # 初始价格
    price = 100.0
    
    # 当前时间戳
    current_timestamp = start_timestamp
    
    # 第一个点固定，之后随机
    data.append((current_timestamp, price))
    
    # 随机生成剩余的点
    for i in range(1, num_points):
        # 随机选择时间增量 - 从30秒到10分钟之间随机
        time_increment = random.randint(30, 600)
        current_timestamp += time_increment
        
        # 检查当前时间戳是否在交易时间内，如果不在则调整
        if not ma.is_trading_time(current_timestamp):
            current_dt = datetime.fromtimestamp(current_timestamp)
            current_date = current_dt.date()
            current_hour = current_dt.hour
            current_minute = current_dt.minute
            
            # 如果在中午休市时间，跳到下午开盘
            if current_hour == 11 and current_minute >= 30 or current_hour == 12:
                afternoon_start = datetime.strptime(f"{current_date.strftime('%Y-%m-%d')} 13:00:00", "%Y-%m-%d %H:%M:%S")
                current_timestamp = afternoon_start.timestamp()
            # 如果在收盘后或开盘前，跳到下一个交易日
            elif current_hour >= 15 or current_hour < 9 or (current_hour == 9 and current_minute < 30):
                # 获取下一个交易日
                next_day = current_date + timedelta(days=1)
                # 跳过周末
                while next_day.weekday() >= 5:
                    next_day += timedelta(days=1)
                
                next_trading_time = datetime.strptime(f"{next_day.strftime('%Y-%m-%d')} 09:30:00", "%Y-%m-%d %H:%M:%S")
                current_timestamp = next_trading_time.timestamp()
        
        # 生成价格变动 (-1% 到 1%)
        price_change_percent = random.uniform(-1.0, 1.0)
        price = price * (1 + price_change_percent / 100)
        
        # 确保价格不会太低
        if price < 90:
            price = 90 + random.uniform(0, 10)
        
        # 添加数据点
        data.append((current_timestamp, price))
    
    print(f"\n已生成{len(data)}个数据点")
    
    # 确保数据点按时间顺序排序
    return sorted(data, key=lambda x: x[0])

def main():
    """主函数"""
    # 获取用户输入
    num_bin, window, start_timestamp, num_points, output_file = get_user_input()
    
    # 创建MovingAverage实例
    ma = MovingAverage(num_bin, window)
    
    # 确保起始时间在交易时间内
    if not ma.is_trading_time(start_timestamp):
        dt = datetime.fromtimestamp(start_timestamp)
        print(f"错误：起始时间 {dt.strftime('%Y-%m-%d %H:%M:%S')} 不在交易时间内")
        
        # 询问是否要调整到最近的交易时间
        adjust = input("是否要调整到最近的交易时间? (y/n): ").strip().lower()
        if adjust != 'y':
            return
        
        # 调整到最近的交易时间
        dt = datetime.fromtimestamp(start_timestamp)
        date_str = dt.strftime('%Y-%m-%d')
        
        # 检查是否可以调整到当天的交易时间
        morning_start = datetime.strptime(f"{date_str} {ma.trading_hours['morning_start']}", "%Y-%m-%d %H:%M:%S")
        morning_end = datetime.strptime(f"{date_str} {ma.trading_hours['morning_end']}", "%Y-%m-%d %H:%M:%S")
        afternoon_start = datetime.strptime(f"{date_str} {ma.trading_hours['afternoon_start']}", "%Y-%m-%d %H:%M:%S")
        afternoon_end = datetime.strptime(f"{date_str} {ma.trading_hours['afternoon_end']}", "%Y-%m-%d %H:%M:%S")
        
        dt_time = dt.time()
        morning_start_time = morning_start.time()
        morning_end_time = morning_end.time()
        afternoon_start_time = afternoon_start.time()
        afternoon_end_time = afternoon_end.time()
        
        # 找到最近的交易时间
        if dt_time < morning_start_time:
            # 如果在上午开盘前，调整到上午开盘时间
            adjusted_dt = morning_start
        elif morning_end_time < dt_time < afternoon_start_time:
            # 如果在中午休市时间，调整到下午开盘时间
            adjusted_dt = afternoon_start
        elif dt_time > afternoon_end_time:
            # 如果在收盘后，调整到下一个交易日的上午开盘时间
            next_day = dt.date() + timedelta(days=1)
            
            # 跳过周末
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
                
            adjusted_dt = datetime.combine(next_day, morning_start_time)
        else:
            # 不应该到达这里
            print("无法调整时间")
            return
            
        start_timestamp = adjusted_dt.timestamp()
        print(f"已调整起始时间为: {adjusted_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 设置日志文件
    ma.set_log_file(output_file)
    
    # 生成完整测试数据集
    print(f"\n开始生成测试数据...")
    test_data = generate_test_data(start_timestamp, num_points)
    
    # 模拟数据到达并计算，每处理一条数据后暂停等待用户输入
    if test_data:
        print(f"\n开始模拟数据流处理...")
        print("每处理一条数据后将暂停，按回车继续...")
        print(f"时间戳\t\t价格\t\tSMA")
        
        for i, (timestamp, value) in enumerate(test_data):
            # 更新数据
            ma.Update(timestamp, value)
            
            # 获取SMA
            sma = ma.GetSMA()
            
            # 打印当前数据点信息
            dt = datetime.fromtimestamp(timestamp)
            print(f"{dt.strftime('%Y-%m-%d %H:%M:%S')}\t{value:.2f}\t{sma:.2f}")
            
            # 暂停等待用户输入
            if i < len(test_data) - 1:  # 如果不是最后一个数据点，则等待用户输入
                input("按回车继续处理下一条数据...")
        
        # 关闭日志文件
        ma.close_log_file()
        
        print(f"\n处理完成，SMA值和相关数据已写入 {output_file}")
        print(f"共处理 {len(test_data)} 个数据点")
    else:
        print("未能生成有效的测试数据")
        ma.close_log_file()

if __name__ == "__main__":
    main() 