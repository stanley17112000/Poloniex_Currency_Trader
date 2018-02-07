# -*- coding: utf-8 -*-
import urllib
import urllib2
import requests
import json
import time
import hmac, hashlib
import random
from progressbar import *

widgets = ['Wait Time (sec): ', Percentage(), ' ', Bar(marker='0',left='[',right=']'),
           ' ', ETA(), ' ', FileTransferSpeed()] #see docs for other options


def createTimeStamp(datestr, format="%Y-%m-%d %H:%M:%S"):
    return time.mktime(time.strptime(datestr, format))


class poloniex:
    def __init__(self, APIKey, Secret):
        self.APIKey = APIKey
        self.Secret = Secret

    def post_process(self, before):
        after = before

        # Add timestamps if there isnt one but is a datetime
        if ('return' in after):
            if (isinstance(after['return'], list)):
                for x in xrange(0, len(after['return'])):
                    if (isinstance(after['return'][x], dict)):
                        if ('datetime' in after['return'][x] and 'timestamp' not in after['return'][x]):
                            after['return'][x]['timestamp'] = float(createTimeStamp(after['return'][x]['datetime']))

        return after

    def api_query(self, command, req={}):

        if (command == "returnTicker" or command == "return24Volume"):
            ret = urllib2.urlopen(urllib2.Request('https://poloniex.com/public?command=' + command))
            return json.loads(ret.read())
        elif (command == "returnOrderBook"):
            ret = urllib2.urlopen(urllib2.Request(
                'https://poloniex.com/public?command=' + command + '&currencyPair=' + str(req['currencyPair'])))
            return json.loads(ret.read())
        elif (command == "returnMarketTradeHistory"):
            ret = urllib2.urlopen(urllib2.Request(
                'https://poloniex.com/public?command=' + "returnTradeHistory" + '&currencyPair=' + str(
                    req['currencyPair'])))
            return json.loads(ret.read())
        else:
            req['command'] = command
            req['nonce'] = int(time.time() * 1000)
            post_data = urllib.urlencode(req)

            sign = hmac.new(self.Secret, post_data, hashlib.sha512).hexdigest()
            headers = {
                'Sign': sign,
                'Key': self.APIKey
            }

            ret = requests.post('https://poloniex.com/tradingApi', data=req, headers=headers)
            jsonRet = json.loads(ret.text)
            return self.post_process(jsonRet)

    def returnTicker(self):
        return self.api_query("returnTicker")

    def return24Volume(self):
        return self.api_query("return24Volume")

    def returnOrderBook(self, currencyPair):
        return self.api_query("returnOrderBook", {'currencyPair': currencyPair})

    def returnMarketTradeHistory(self, currencyPair):
        return self.api_query("returnMarketTradeHistory", {'currencyPair': currencyPair})

    # Returns all of your balances.
    # Outputs:
    # {"BTC":"0.59098578","LTC":"3.31117268", ... }
    def returnBalances(self):
        return self.api_query('returnBalances')

    # Returns your open orders for a given market, specified by the "currencyPair" POST parameter, e.g. "BTC_XCP"
    # Inputs:
    # currencyPair  The currency pair e.g. "BTC_XCP"
    # Outputs:
    # orderNumber   The order number
    # type          sell or buy
    # rate          Price the order is selling or buying at
    # Amount        Quantity of order
    # total         Total value of order (price * quantity)
    def returnOpenOrders(self, currencyPair):
        return self.api_query('returnOpenOrders', {"currencyPair": currencyPair})

    # Returns your trade history for a given market, specified by the "currencyPair" POST parameter
    # Inputs:
    # currencyPair  The currency pair e.g. "BTC_XCP"
    # Outputs:
    # date          Date in the form: "2014-02-19 03:44:59"
    # rate          Price the order is selling or buying at
    # amount        Quantity of order
    # total         Total value of order (price * quantity)
    # type          sell or buy
    def returnTradeHistory(self, currencyPair):
        return self.api_query('returnTradeHistory', {"currencyPair": currencyPair})

    # Places a buy order in a given market. Required POST parameters are "currencyPair", "rate", and "amount". If successful, the method will return the order number.
    # Inputs:
    # currencyPair  The curreny pair
    # rate          price the order is buying at
    # amount        Amount of coins to buy
    # Outputs:
    # orderNumber   The order number
    def buy(self, currencyPair, rate, amount):
        return self.api_query('buy', {"currencyPair": currencyPair, "rate": rate, "amount": amount})

    # Places a sell order in a given market. Required POST parameters are "currencyPair", "rate", and "amount". If successful, the method will return the order number.
    # Inputs:
    # currencyPair  The curreny pair
    # rate          price the order is selling at
    # amount        Amount of coins to sell
    # Outputs:
    # orderNumber   The order number
    def sell(self, currencyPair, rate, amount):
        return self.api_query('sell', {"currencyPair": currencyPair, "rate": rate, "amount": amount})

    # Cancels an order you have placed in a given market. Required POST parameters are "currencyPair" and "orderNumber".
    # Inputs:
    # currencyPair  The curreny pair
    # orderNumber   The order number to cancel
    # Outputs:
    # succes        1 or 0
    def cancel(self, currencyPair, orderNumber):
        return self.api_query('cancelOrder', {"currencyPair": currencyPair, "orderNumber": orderNumber})

    # Immediately places a withdrawal for a given currency, with no email confirmation. In order to use this method, the withdrawal privilege must be enabled for your API key. Required POST parameters are "currency", "amount", and "address". Sample output: {"response":"Withdrew 2398 NXT."}
    # Inputs:
    # currency      The currency to withdraw
    # amount        The amount of this coin to withdraw
    # address       The withdrawal address
    # Outputs:
    # response      Text containing message about the withdrawal
    def withdraw(self, currency, amount, address):
        return self.api_query('withdraw', {"currency": currency, "amount": amount, "address": address})


class cur_trader:

    MID_PRICE = 1
    TAKER_PRICE = 2

    def __init__(self, account):
        self.account = account


    def setTicker(self, ticker):
        self.ticker = ticker

    def setOrderBook(self, orderBook):
        self.orderBook = orderBook

    # transfer {amout} ori_cur -> new+cur
    def __execute_trade(self, ori_cur, new_cur, amount, wait_maxi_sec=300, method=MID_PRICE):

        orderBook = self.orderBook
        t_str = ori_cur + "_" + new_cur
        t_str_rev = new_cur + "_" + ori_cur

        if t_str in orderBook:
            # ori_cur to new_cur
            # buy order

            asks = orderBook[t_str][ 'asks' ]
            bids = orderBook[t_str][ 'bids' ]
            lowest_ask = float(asks[0][0])
            highest_bid = float(bids[0][0])


            if method == self.MID_PRICE:
                mid_price = (highest_bid + lowest_ask) / 2
            elif method == self.TAKER_PRICE:
                mid_price = lowest_ask

            new_amount = amount / mid_price

            print 'Executing Buy operation {} {} -> {} {}'.format( amount, ori_cur , new_amount, new_cur  )
            #check whether buy operation success
            result = account.buy(t_str, mid_price, new_amount)
            if 'error' in result:
                print 'Currency Pair : {},  {} -> {} failed!!!  msg: {}'.format( t_str, ori_cur, new_cur, result['error'] )
                return None
            print 'Buy orders : {}'.format( result )
            order_number = result['orderNumber']


            start_time = time.time()

            pbar = ProgressBar(widgets=widgets, maxval=wait_maxi_sec)
            pbar.start()
            pbar.update(0)
            print 'Proccessing {}   {} {} -> {} {} : rate is {} '.format(t_str, ori_cur, amount, new_cur, new_amount, mid_price)

            while True:

                orders = account.returnOpenOrders(t_str)
                if 'error' in orders:
                    print 'Error : {}'.format( orders['error'] )
                    return None

                if len(orders) == 0:
                    pbar.finish()
                    return new_amount
                else:
                    still_pending = False
                    for order in orders:
                        if order['orderNumber'] == order_number:
                            still_pending = True
                            break

                if not still_pending:
                    pbar.finish()
                    return new_amount

                time.sleep(10)
                new_time = min( wait_maxi_sec-1, time.time()-start_time )
                pbar.update( new_time )

                if new_time+1 >= wait_maxi_sec:
                    account.cancel(t_str, orders[0]['orderNumber'])
                    pbar.finish()
                    print 'Time limit exceed'
                    return None


        elif t_str_rev in ticker:
            # new_cur/ori_cur
            # sell order
            asks = orderBook[t_str_rev]['asks']
            bids = orderBook[t_str_rev]['bids']
            lowest_ask = float(asks[0][0])
            highest_bid = float(bids[0][0])

            if method == self.MID_PRICE:
                mid_price = ( lowest_ask + highest_bid ) / 2
            elif method == self.TAKER_PRICE:
                mid_price = highest_bid


            new_amount = amount * mid_price
            result = account.sell(t_str_rev, mid_price, amount)
            order_number = result['orderNumber']
            print result
            print 'Executing Sell operation {} {} -> {} {}'.format( amount, ori_cur, new_amount, new_cur )
            # check whether sell operation success
            if 'error' in result:
                print 'Currency Pair : {},  {} -> {} failed!!!  msg: {}'.format(t_str_rev, ori_cur, new_cur, result['error'])
                return None

            start_time = time.time()
            pbar = ProgressBar(widgets=widgets, maxval=wait_maxi_sec)
            pbar.start()
            pbar.update(0)
            print 'Proccessing {}   {} {} -> {} {} : rate is {} '.format(t_str_rev,amount, ori_cur, new_amount,
                                                                              new_cur, mid_price)
            while True:

                orders = account.returnOpenOrders(t_str_rev)
                if 'error' in orders:
                    print 'Error : {}'.format( orders['error'] )
                    return None


                if len(orders) == 0:
                    pbar.finish()
                    return new_amount
                else:
                    still_pending = False
                    for order in orders:
                        if order['orderNumber'] == order_number:
                            still_pending = True
                            break

                if not still_pending:
                    pbar.finish()
                    return new_amount

                time.sleep(10)

                new_time = min( wait_maxi_sec-1 , time.time() - start_time )
                pbar.update( new_time )

                if new_time + 1 >= wait_maxi_sec:
                    account.cancel(t_str_rev, orders[0]['orderNumber'])
                    pbar.finish()
                    print 'Time limit exceed'
                    return None
        else:
            print 'Error : Currency transform of {} -> {} not occured'.format( ori_cur, new_cur )
            return None



    def start_trade(self, path, maxi_wait_sec=10, method=MID_PRICE):

        if len( path ) < 1:
            return

        ori_cur = path[0]
        amount = float( self.account.returnBalances()[ ori_cur ] )

        for i in range( 1, len(path) ):
            new_cur = path[i]

            execute_success = self.__execute_trade( ori_cur, new_cur, amount, maxi_wait_sec, method )

            if execute_success:
                new_amount =  float( self.account.returnBalances()[ new_cur ] )
                print 'Successfully transfered {}{} -> {}{}'.format( amount, ori_cur, new_amount, new_cur )
                amount  = new_amount
                ori_cur = new_cur
            else:
                print 'Trade canceled'
                return

        return




class currency_transferer:


        MID_PRICE = 1
        TAKER_PRICE = 2


        # currencies used to evaluate the value of assets

        evaluate_dict = {}
        evaluate_dict['USDT'] = ['BTC', 'ETH', 'XMR']
        evaluate_dict['BTC']  = ['ETH', 'XRP', 'LTC', 'USDT']

        def __init__(self, balance, ticker, orderBook, method=MID_PRICE):
            self.balance = balance
            self.ticker  = ticker
            self.orderBook = orderBook
            self.method = method

        def show_coin_path(self, path, value ):
            prev = path[0]
            print '{} : {} '.format( prev , value),
            for i in range( 1, len(path) ):
                now = path[i]
                value = transferer.to_other_currency( prev, now, value )
                prev = now
                print ' ---> {} : {}'.format( now, value ),

            print ''

        def get_coin_rates(self, max_depth=1):

            # store the trades    from the begin currency to the maximum of each currency
            # trades[ {trade_count} ][ {currency} ]
            # e.g. trades[0]['BTC'] = 1
            #      trades[1]['BTC'] = 1.001    trades[1]['ETH'] = 0.01
            self.trades = []
            # store the trade sources of each currency
            # trades[ {trade_count} ][ {currency} ]
            # e.g. trades[0]['BTC'] = 'BTC'
            # e.g. trades[1]['ETH'] = 'BTC'
            # e.g. trades[2]['XMR'] = 'ETH'
            self.sources = []

            for i in range( max_depth+1 ):
                self.trades.append( {} )
                self.sources.append( {} )

            self.trades[0] =  dict( self.balance )
            for key in self.trades[0]:
                self.trades[0][key] = float( self.trades[0][key] )
                self.sources[0][key] = key

            for iter in range( 1, max_depth+1 ):

                for key in self.trades[iter-1]:
                    self.trades[iter][key] = self.trades[iter-1][key]
                    self.sources[iter][key] = key

                # to currency
                for last in self.balance:
                    # from currency
                    for beg in self.balance:

                        change_val = self.to_other_currency( beg, last, self.trades[iter-1][beg] )
                        if change_val is None:
                            change_val = 0

                        if beg != last and  change_val > self.trades[iter][last]:
                            self.trades[iter][last] = change_val
                            self.sources[iter][last] = beg


            return self.trades, self.sources

        def to_valuate_currency(self, ori_cur, valuate_currency, amount):
            # RETURN None if cannot find transfer way of currency
            if valuate_currency in self.evaluate_dict:

                # get the middle currency to transform from ori_cur -> mid_cid -> valuate_cur
                # e.g. valuate_cur_arr = ['ETH', 'XMR' ... ] for BTC
                valuate_cur_arr = self.evaluate_dict[valuate_currency]

                valuate_currency_amount = self.to_other_currency( ori_cur, valuate_currency, amount )

                if valuate_currency_amount:
                    return valuate_currency_amount

                for mid_currency in valuate_cur_arr:
                    mid_cur_amount = self.to_other_currency( ori_cur, mid_currency, amount )
                    if mid_cur_amount:
                        final_cur_amount = self.to_other_currency( mid_currency, valuate_currency, mid_cur_amount )
                        if final_cur_amount:
                            return final_cur_amount

            return None

        def to_other_currency(self, ori_cur, new_cur , amount):

            if ori_cur == new_cur:
                return float(amount)

            # to check whether orderBook exists pair of {ori_cur}_{new_cur}
            t_str = ori_cur + "_" + new_cur
            # to check whether orderBook exists pair of {new_cur}_{ori_cur}
            t_str_rev = new_cur + "_" + ori_cur

            currency_pair = None

            amount = float( amount )

            if t_str in self.orderBook:
                currency_pair = t_str
                rev = False
            elif t_str_rev in self.orderBook:
                currency_pair = t_str_rev
                rev = True
            else:
                return None

            asks = self.orderBook[ currency_pair ][ 'asks' ]
            bids = self.orderBook[ currency_pair ][ 'bids' ]

            if len( asks ) == 0 or len( bids ) == 0:
                return None

            lowest_ask = float(asks[0][0])
            highest_bid = float(bids[0][0])

            if self.method == self.MID_PRICE:
                price = (highest_bid + lowest_ask) / 2
            elif self.method == self.TAKER_PRICE:
                # t_str buy order
                if currency_pair == t_str:
                    price = lowest_ask
                else:
                    price = highest_bid

            if rev:
                return amount * price
            else:
                return amount / price



if __name__ == '__main__':

    account = poloniex( 'Public Key', 'Secret Key' )

    # open orders will be terminated if exceed this time limit
    # in seconds
    trade_limit_time = 1800

    # minimum amount to execute trade
    mini_evaluate_value_to_execute = 0.001

    # the final currency of the account
    valuate_cur = 'BTC'



    minimum_profit_gain_to_executes = [0.01, 0.01, 0.01, 0.005, 0.008, 0.01]

    while True:
        # the maximum search depth of currency transfer
        maxi_depth = random.randint( 3, 5 )
        minimum_profit_gain_to_execute = minimum_profit_gain_to_executes[ maxi_depth ]
        # total amount of account.  Ex. net_total = { 'BTC': 0.3, 'USDT' : 0.5 }
        net_total = {}

        net_total[valuate_cur] = 0

        # account balance
        balance = account.returnBalances()

        # current ticker
        ticker  = account.returnTicker()

        orderBook = account.returnOrderBook( 'all' )

        # the default currency transferer
        transferer = currency_transferer( balance, ticker, orderBook , currency_transferer.TAKER_PRICE )

        for cur in balance:
            net_total[ cur ] = 0

        for cur in balance:
            # the transformed value of valuate currency
            # e.g.   cur = 'XMR'  valuate_cur = 'BTC'
            # transform XMR to equal amount of valuate_cur
            valuate_cur_amount = transferer.to_valuate_currency( cur, valuate_cur , balance[cur] )
            if valuate_cur_amount:
                net_total[valuate_cur] += valuate_cur_amount
            elif float( balance[cur] ) > 0:
                net_total[cur] = balance[cur]

        print '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'
        print 'Currently net total : {}  '.format( net_total )
        print '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'

        # the profit gain should be at least
        best_profits = 0
        best_ori_money = 0
        best_strategy = None

        for cur in balance:

            evaluate_value = transferer.to_valuate_currency( cur, valuate_cur, balance[cur] )

            if (evaluate_value is None) or evaluate_value < mini_evaluate_value_to_execute:
                continue

            # set starting cur = balance[cur]
            # set other cur = 0
            tmp_balance = dict( balance )
            for t_cur in tmp_balance:
                if t_cur != cur:
                    tmp_balance[t_cur] = 0

            # temp transferer
            tmp_transferer = currency_transferer( tmp_balance, ticker, orderBook , currency_transferer.TAKER_PRICE )

            trades, sources = tmp_transferer.get_coin_rates( maxi_depth )

            maxi_value = 0
            strategy = None

            # check the value of transforming cur ->  evaluate_cur

            value = trades[maxi_depth-1][valuate_cur]
            if value and value > evaluate_value and value > maxi_value:
                path = [  ]
                path.append( valuate_cur )
                now = valuate_cur
                it = maxi_depth - 1
                while it > 0:
                    now = sources[it][now]
                    it -= 1
                    path.append(now)

                path.reverse()
                remove_same_path = [path[0]]
                for i in range(1, len(path) ):

                    if path[i] != path[i - 1]:
                        remove_same_path.append(path[i])

                extra_value = value - evaluate_value
                profit_gain = extra_value / evaluate_value
                if profit_gain > best_profits:
                    best_profits = profit_gain
                    best_strategy = remove_same_path
                    best_ori_money = evaluate_value

        print best_strategy
        print best_profits
        if best_strategy and (best_profits > minimum_profit_gain_to_execute):

            print 'Estimated Profit : {}% '.format( best_profits*100  )
            print 'Strategy : {}'.format( best_strategy  )
            print 'Original {} : {} ---> {} {}'.format( cur, best_strategy[0], valuate_cur, best_ori_money )
            transferer.show_coin_path( best_strategy, balance[ best_strategy[0] ] )
            trader = cur_trader(account)
            trader.setTicker( ticker )
            trader.setOrderBook( orderBook )
            trader.start_trade(best_strategy, trade_limit_time , cur_trader.TAKER_PRICE)
        else:
            print 'Profit not enough to execute'



        print 'Preparing Next Trade ...'
        time.sleep(3)



