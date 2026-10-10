import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from market_data.schema import normalize,validate,merge_frames,aggregate,quality,align_available,utc,duration
from market_data.source import archive,MissingArchive,rest_tail
from market_data.store import publish,writer_lock,read_market


def rows(n=12,start='2024-01-01',unit='ms'):
    first=utc(start);out=[]
    multiplier=1000 if unit=='ms' else 1000000
    for i in range(n):
        t=int((first+pd.Timedelta(minutes=5*i)).timestamp()*multiplier)
        out.append([t,100,102,99,101,2,t+300*multiplier-1,201,5,1,100,0])
    return out

def frame(n=12,start='2024-01-01'):
    return normalize(rows(n,start),'5m',utc(start)+pd.Timedelta(minutes=5*n))[0]

class DatabaseTests(unittest.TestCase):
    def test_millisecond_microsecond_equivalence(self):
        a,_=normalize(rows(unit='ms'),'5m',utc('2024-01-02'))
        b,_=normalize(rows(unit='us'),'5m',utc('2024-01-02'))
        pd.testing.assert_frame_equal(a,b)
    def test_incomplete_excluded_at_exact_boundary(self):
        a,n=normalize(rows(2),'5m',utc('2024-01-01T00:05:00Z'))
        self.assertEqual((len(a),n),(1,1))
        self.assertEqual(a.available_at.iloc[0],utc('2024-01-01T00:05Z'))
    def test_inclusive_close_invalid(self):
        r=rows(1);r[0][6]+=1
        with self.assertRaises(ValueError):normalize(r,'5m',utc('2024-01-02'))
    def test_off_grid_invalid(self):
        r=rows(1);r[0][0]+=1;r[0][6]+=1
        with self.assertRaises(ValueError):normalize(r,'5m',utc('2024-01-02'))
    def test_ohlc_nonfinite_negative_invalid(self):
        for col,value in [(2,99),(5,-1),(4,float('nan')),(8,1.5)]:
            r=rows(1);r[0][col]=value
            with self.assertRaises(ValueError):normalize(r,'5m',utc('2024-01-02'))
    def test_duplicate_idempotence_and_conflict(self):
        a=frame();b,count=merge_frames([a,a],'5m')
        self.assertEqual(count,12);pd.testing.assert_frame_equal(a,b)
        bad=a.copy();bad.loc[0,'close']=100
        with self.assertRaises(ValueError):merge_frames([a,bad],'5m')
    def test_known_aggregation_and_gap_not_filled(self):
        a=frame();b=aggregate(a,'15m')
        self.assertEqual(len(b),4);self.assertEqual(b.volume.iloc[0],6)
        self.assertEqual(b.trades.iloc[0],15)
        self.assertEqual(b.available_at.iloc[0],utc('2024-01-01T00:15Z'))
        gap=aggregate(a.drop(index=1).reset_index(drop=True),'15m')
        self.assertEqual(len(gap),3);self.assertEqual(gap.open_time.iloc[0],utc('2024-01-01T00:15Z'))
    def test_daily_utc_boundary(self):
        a=frame(288);b=aggregate(a,'1d')
        self.assertEqual(len(b),1);self.assertEqual(b.available_at.iloc[0],utc('2024-01-02'))
        self.assertTrue(aggregate(a.iloc[:-1],'1d').empty)
    def test_gap_ranges_including_requested_edges(self):
        a=frame(12).iloc[1:-1].drop(index=5).reset_index(drop=True)
        q=quality(a,'5m','2024-01-01','2024-01-01T01:00Z')
        self.assertEqual(q['missing_candles'],3);self.assertEqual(len(q['gaps']),3)
    def test_alignment_preclose_exact_and_stale(self):
        f=aggregate(frame(12),'1h')
        ds=['2024-01-01T00:59Z','2024-01-01T01:00Z','2024-01-01T01:59Z','2024-01-01T02:00Z']
        r=align_available(ds,f,['close'],'1h')
        self.assertTrue(np.isnan(r.close.iloc[0]));self.assertEqual(r.close.iloc[1],101)
        self.assertEqual(r.close.iloc[2],101);self.assertTrue(np.isnan(r.close.iloc[3]))
    def test_future_candles_cannot_change_completed_aggregate(self):
        a=frame(24);before=aggregate(a.iloc[:12],'1h');a.loc[12:,'high']=999
        after=aggregate(a,'1h').iloc[:1].reset_index(drop=True)
        pd.testing.assert_frame_equal(before,after)
    def test_parquet_roundtrip_idempotence_protected_read_and_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            a=frame();report={'start':'2024-01-01T00:00Z','cutoff':'2024-01-01T01:00Z'}
            cat,stats=publish(td,{'5m':a},report,[])
            self.assertEqual(stats['written_partitions'],1)
            _,second=publish(td,{'5m':a},report,[]);self.assertEqual(second['reused_partitions'],1)
            b=read_market(td,'5m',report['start'],report['cutoff']);pd.testing.assert_frame_equal(a,b)
            with self.assertRaises(PermissionError):read_market(td,'5m','2026-04-01','2026-04-02')
            path=Path(td)/cat['partitions'][0]['path'];path.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):read_market(td,'5m',report['start'],report['cutoff'])
    def test_reader_rejects_gap_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            a=frame().drop(index=1).reset_index(drop=True)
            report={'start':'2024-01-01T00:00Z','cutoff':'2024-01-01T01:00Z'}
            publish(td,{'5m':a},report,[])
            with self.assertRaises(ValueError):read_market(td,'5m',report['start'],report['cutoff'])
            self.assertEqual(len(read_market(td,'5m',report['start'],report['cutoff'],allow_gaps=True)),11)
    def test_writer_lock_and_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            with writer_lock(td):
                with self.assertRaises(RuntimeError):
                    with writer_lock(td):pass
            self.assertFalse((Path(td)/'sync.lock').exists())
    def test_checksum_failure_does_not_cache(self):
        with tempfile.TemporaryDirectory() as td:
            with patch('market_data.source.get',side_effect=[b'0'*64+b' file.zip',b'bad']):
                with self.assertRaises(ValueError):archive(td,'2024-01')
            self.assertFalse(list(Path(td).rglob('*.zip')))
    def test_cached_archive_revalidates_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            raw=b'test';sha=hashlib.sha256(raw).hexdigest()
            with patch('market_data.source.get',side_effect=[sha.encode()+b' file.zip',raw]):archive(td,'2024-01')
            with patch('market_data.source.get',side_effect=AssertionError('network')):
                _,meta=archive(td,'2024-01');self.assertTrue(meta['cached'])
    def test_rest_pagination_and_partial(self):
        with tempfile.TemporaryDirectory() as td:
            with patch('market_data.source.get',side_effect=[json.dumps(rows(2)).encode(),json.dumps(rows(2,'2024-01-01T00:10Z')).encode()]):
                frames,meta,n=rest_tail(td,'2024-01-01','2024-01-01T00:17Z')
            self.assertEqual(sum(len(x) for x in frames),3);self.assertEqual(n,1)
            self.assertEqual(len(meta),2)

    def test_timestamp_anomaly_quarantine_is_explicit(self):
        r=rows(3);r[1][6]-=100
        quarantine=[]
        a,_=normalize(r,'5m',utc('2024-01-02'),quarantine=quarantine)
        self.assertEqual(len(a),2);self.assertEqual(len(quarantine),1)
        self.assertEqual(quarantine[0]['reason'],'nonstandard_close_boundary')
        self.assertEqual(quality(a,'5m','2024-01-01','2024-01-01T00:15Z')['missing_candles'],1)
    def test_incremental_month_extension_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as td:
            report={'start':'2024-01-01T00:00Z','cutoff':'2024-01-01T01:00Z'}
            old,_=publish(td,{'5m':frame()},report,[])
            later={'start':report['start'],'cutoff':'2024-01-01T02:00Z'}
            new,stats=publish(td,{'5m':frame(24)},later,[])
            self.assertEqual(stats['written_partitions'],1)
            self.assertTrue((Path(td)/old['partitions'][0]['path']).exists())
            self.assertNotEqual(old['snapshot_id'],new['snapshot_id'])
            before=(Path(td)/'catalog.json').read_bytes()
            broken=frame();broken.loc[0,'high']=0
            with self.assertRaises(ValueError):publish(td,{'5m':broken},report,[])
            self.assertEqual(before,(Path(td)/'catalog.json').read_bytes())

if __name__=='__main__':unittest.main()
