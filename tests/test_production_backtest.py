import numpy as np
import pandas as pd
import pytest
from macro_allocation.production_backtest import run_backtest
from macro_allocation.errors import DataValidationError

def inputs():
    idx=pd.date_range("2020-01-31",periods=4,freq="ME")
    pos=pd.DataFrame({"CREDIT":[1,-1,1,1]},index=idx)
    ret=pd.DataFrame({"CREDIT":[.01,.02,.03,.04]},index=idx)
    cash=pd.Series([.001]*4,index=idx)
    return idx,pos,ret,cash

def test_lag_cost_cash_and_compounding_contract():
    idx,pos,ret,cash=inputs(); result=run_backtest(pos,ret,cash,{"CREDIT":1},10,"2020-02-29")
    assert result.allocations.CREDIT.tolist()==[1,-1,1]
    assert (result.rebalance.signal_date < result.rebalance.execution_date).all()
    assert np.allclose(result.monthly.transaction_cost,result.monthly.turnover*.001)
    assert np.isclose(result.monthly.iloc[0].gross_return,.02)

def test_key_mismatch_is_fatal():
    idx,pos,ret,cash=inputs()
    with pytest.raises(DataValidationError,match="keys must match"):
        run_backtest(pos,ret,cash,{"SHORT_BOND":1},10,"2020-02-29")

def test_missing_return_is_never_zero():
    idx,pos,ret,cash=inputs(); ret.iloc[1,0]=np.nan
    with pytest.raises(DataValidationError,match="cannot be treated as zero"):
        run_backtest(pos,ret,cash,{"CREDIT":1},10,"2020-02-29")

def test_allow_short_defaults_to_original_long_short_behaviour():
    idx,pos,ret,cash=inputs()
    default=run_backtest(pos,ret,cash,{"CREDIT":1},10,"2020-02-29")
    explicit=run_backtest(pos,ret,cash,{"CREDIT":1},10,"2020-02-29",allow_short=True)
    pd.testing.assert_frame_equal(default.allocations,explicit.allocations)
    pd.testing.assert_frame_equal(default.monthly,explicit.monthly)
    assert default.allocations.CREDIT.min()==-1

def test_long_only_clips_short_positions_into_cash():
    idx,pos,ret,cash=inputs()
    result=run_backtest(pos,ret,cash,{"CREDIT":1},10,"2020-02-29",allow_short=False)
    assert result.allocations.CREDIT.tolist()==[1,0,1]
    assert result.allocations.CASH.tolist()==[0,1,0]
    assert (result.allocations.drop(columns="CASH")>=0).all().all()
    # The clipped month earns the cash return instead of a short CREDIT return.
    assert np.isclose(result.monthly.iloc[1].gross_return,.001)
    assert np.allclose(result.monthly.turnover,[1,1,1])

def test_allow_short_must_be_boolean():
    idx,pos,ret,cash=inputs()
    with pytest.raises(DataValidationError,match="allow_short"):
        run_backtest(pos,ret,cash,{"CREDIT":1},10,"2020-02-29",allow_short="false")
