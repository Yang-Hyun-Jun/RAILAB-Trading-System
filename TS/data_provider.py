from abc import ABCMeta, abstractmethod

class DataProvider(metaclass=ABCMeta):
    """
    데이터 소스로부터 데이터를 수집해서 
    정해진 형태로 제공하기 위한 클래스의 추상클래스
    """

    @abstractmethod
    def get_info(self):
        """
        현재 거래 정보를 딕셔너리 타입으로 반환

        Returns
        {
            "market": 거래 시장 종류 BTC
            "date_time": 정보의 기준 시간
            "opening_price": 시작 거래 가격
            "high_price": 최고 거래 가격
            "low_price": 최저 거래 가격
            "closing_price": 마지막 거래 가격
            "acc_price": 단위 시간내 누적 거래 금액
            "acc_volume": 단위 시간내 누적 거래 양
        }
        """

