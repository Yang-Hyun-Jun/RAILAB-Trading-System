import copy
import time

from datetime import datetime
from urllib import request
from .strategy import Stratgy
from .log_manager import LogManager


class StrategyBuyAndHold(Stratgy):
    """
    B&H 전략

    isInitialized: 최초 잔고는 초기화 할 때만 갱신 된다. 
    data: 종목 데이터 리스트, OHLCV 데이터
    result: 주문 결과 리스트
    request: 마지막 거래 요청
    budget: 시작 잔고
    balance: 현재 잔고
    min_price: 최소 주문 금액
    """

    ISO_DATEFORMAT = "%Y-%m-%dT%H:%M:%S"
    COMMISSION_RATIO = 0.0005

    def __init__(self):
        self.is_initialized = False
        self.is_simulation = False
        self.data = []
        self.budget = 0
        self.balance = 0.0 
        self.min_price = 0
        self.result = []
        self.request = None
        self.logger = LogManager.get_logger(__class__.__name__)
        self.name = "BnH"
        self.waiting_requests = {}

    def initialize(self, budget, min_price=0):
        """
        예산과 최소 거래 가능 금액을 설정 
        """
        if self.is_initialized:
            return
        
        self.is_initialized = True
        self.budget = budget
        self.balance = budget
        self.min_price = min_price

    def update_trading_info(self, info):
        """
        새로운 종목 데이터 추가

        info:
        {
            "market": 거래 시장 종류 BTC,
            "date_time": 정보의 기준 시간, 
            "opening_price": 시가,
            "high_price": 고가,
            "low_price": 저가,
            "clsoing_price": 종가,
            "acc_price": 단위 시간내 누적 거래 금액,
            "acc_volume": 단위 시간내 누적 거래 양
        }
        """

        if self.is_initialized is not True: 
            return
        self.data.append(copy.deepcopy(info))

    def get_request(self):
        """
        데이터 분석 결과에 따라 주문 생성
        
        5번에 걸쳐 시장가로 분할 매수 후 홀딩하는 전략
        마지막 종가로 처음 예산의 1/5에 해당하는 양 만큼 매수 시도
        
        returns: 리스트에 한 개 이상의 주문 정보 전달
        [{

            "id": 요청 정보 id "1607862457.560075"
            "type": 거래 유형 sell, buy, cancel
            "price": 주문 가격
            "amount": 주문 수량
            "date_time": 요청 생성 시간, 시뮬레이션에서는 데이터 시간
        }]
        """
        signal = False

        if self.is_initialized is not True:
            return 
        
        try:
            if len(self.data) == 0 or self.data[-1] is None:
                raise UserWarning("Data is empty")

            last_closing_price = self.data[-1]["closing_price"]
            now_time = datetime.now().strftime(self.ISO_DATEFORMAT)

            if self.is_simulation:
                now_time = self.data[-1]["date_time"]

            # 예산의 1/5을 주문 금액으로 설정
            # 주문 금액보다 잔액이 부족할 경우 잔액 만큼 주문
            target_price = self.budget / 5
            if target_price > self.balance:
                target_price = self.balance

            # 주문 수량 = 주문 금액 / 현재 종가
            # 업비트의 경우 소수점 아래 5자리 이상은 주문 불가
            amount = round(target_price / last_closing_price, 4) 
            
            # 신규 주문 정보 생성
            trading_request = {
                "id": str(round(time.time(), 3)),
                "type": "buy",
                "price": target_price,
                "amount": amount,
                "date_time": now_time}

            if self.min_price > target_price:
                raise UserWarning("Total value is smaller than min price")
            if self.balance < target_price:
                raise UserWarning("Balance is smaller than total value")

            # Info 로깅
            self.logger.info(f"[REQUEST] id: {trading_request['id']} =====================")
            self.logger.info(f"price : {last_closing_price}, amount: {amount}")
            self.logger.info(f"type: buy, target price: {target_price}")
            self.logger.info("=====================================================")

            # 신규 주문 생성 시점에서 여전히 체결 대기 상태인 이전 주문은 취소 주문으로 변경하여 추가
            final_requests = []
            for request_id in self.waiting_requests:
                self.logger.info(f"Cancel request added! {request_id}")

                # 체결 대기인 이전 주문부터 최종 요청 리스트에 추가 (리스트 순대로 주문)
                final_requests.append(
                    {
                        "id": request_id,
                        "type": "cancel",
                        "price": 0,
                        "amount": 0,
                        "date_time": now_time
                    })

            # 신규 주문 최종 요청 리스트에 추가
            final_requests.append(trading_request)
            return final_requests, signal
    

        except (ValueError, KeyError) as msg:
            self.logger.error(f"Invalid data {msg}")
        except IndexError:
            self.logger.error("empty data")
        except AttributeError as msg:
            self.logger.error(msg)
        except UserWarning as msg:
            self.logger.info(msg)
            # 시뮬에서는 싱크를 맞추기 위해 항상 주문 생성
            if self.is_simulation:
                return [
                    {
                        "id": str(round(time.time(), 3)),
                        "type": "buy",
                        "price": 0,
                        "amount": 0,
                        "date_time": now_time
                    }]
            return None

            
    def update_result(self, result):
        """
        요청한 주문의 결과를 업데이트
        (1) 체결 대기 및 체결 완료 주문들을 관리
        (2) 잔고 계산

        result:
        {
            "request": 요청 정보
            "type": 거래 유형 sell, buy, cancel
            "price": 거래 가격
            "amount": 거래 수량 
            "msg": 거래 결과 메시지
            "state": 거래 상태 requested, done
            "date_time": 시뮬레이션에서는 데이터 시간 +2초

        }
        """

        if self.is_initialized is not True:
            return
    
        try:
            request = result["request"]

            # 특정 주문이 대기 상태인 경우 대기 주문 딕셔너리에 추가하고 종료
            if result["state"] == "requested":
                self.waiting_requests[request["id"]] = result
                return

            # 대기 주문이 체결된 경우 대기 주문 딕셔너리에서 삭제
            if result["state"] == "done" and request["id"] in self.waiting_requests:
                del self.waiting_requests[request["id"]]

            total = float(result["price"]) * float(result["amount"])
            fee = total * self.COMMISSION_RATIO
            
            # 잔고 계산 (체결된 경우에만)
            if result["type"] == "buy":
                self.balance -= round(total + fee)
            else:
                self.balance += round(total - fee)

            self.logger.info(f"[RESULT] id: {result['request']['id']} ================")
            self.logger.info(f"type: {result['type']}, msg: {result['msg']}")
            self.logger.info(f"price: {result['price']}, amount: {result['amount']}")
            self.logger.info(f"total: {total}, balance: {self.balance}")
            self.logger.info("================================================")
            self.result.append(copy.deepcopy(result))

        except (AttributeError, TypeError) as msg:
            self.logger.error(msg)