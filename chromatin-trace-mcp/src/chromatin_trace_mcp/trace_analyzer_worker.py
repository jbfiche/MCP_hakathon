"""Isolated native analyzer runner. Capture existing returns/plot data; never recalculate."""
import argparse
import contextlib
import json
import traceback
import warnings
from pathlib import Path
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np
from traceratops import trace_analyzer as native


def run(output_format, distance_range, seed):
    arrays, calls, returns, caught = {}, [], {}, []
    stage = ['']

    def save(value, label):
        array = np.asarray(value)
        if array.dtype.kind not in 'biufc': raise TypeError(f'Unsupported native numeric plotting dtype: {array.dtype}')
        key = f'a{len(arrays):04d}_{label}'
        arrays[key] = array.copy()
        if np.ma.isMaskedArray(value):arrays[key+'_mask'] = np.ma.getmaskarray(value).copy()
        return key

    def intercept(name, original):
        def wrapper(ax, *args, **kwargs):
            result = original(ax, *args, **kwargs)
            record = {'stage':stage[0], 'method':name, 'arrays':{}}
            data = args[0] if args else kwargs.get('x', kwargs.get('dataset', kwargs.get('X')))
            if name=='hist':
                record['arrays'] = {'observations':save(data,'observations'),'counts':save(result[0],'counts'),'edges':save(result[1],'edges')}
            elif name=='violinplot':
                record['datasets'] = [save(v,'bootstrap') for v in data]
                record['_axes'] = ax
            elif name=='imshow':record['arrays']['values'] = save(data,'image_values')
            elif name=='hexbin':
                y = args[1] if len(args)>1 else kwargs['y']
                record['arrays'] = {'x':save(data,'x'),'y':save(y,'y'),
                                    'bin_values':save(result.get_array(),'bin_values'), 'bin_centers':save(result.get_offsets(),'bin_centers')}
            calls.append(record)
            return result
        return wrapper

    def tagged(name, original):
        def wrapped(*args, **kwargs):
            previous=stage[0];stage[0]=name
            try:
                result=original(*args, **kwargs)
                if name=='neighbor_distances':returns['neighbor_statistics']=dict(zip(['mean_dx','mean_dy','mean_dz','std_dx','std_dy','std_dz'],map(float,result)))
                return result
            finally:stage[0]=previous
        return wrapped

    barcode_method = native.ChromatinTraceTable.barcode_statistics
    def capture_barcodes(self, *args, **kwargs):
        result=barcode_method(self,*args,**kwargs)
        returns['barcode_multiplicities']={key:save(values,'multiplicities') for key,values in result.items()}
        return result

    success=False;error=None
    try:
        np.random.seed(seed)
        with contextlib.ExitStack() as stack, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            for method in ['hist','violinplot','imshow','hexbin']:
                stack.enter_context(patch.object(Axes,method,intercept(method,getattr(Axes,method))))
            for name, tag in [('get_barcode_statistics','trace_statistics'),('barcode_detection_efficiency','barcode_detection'),
                              ('plot_neighbor_distances','neighbor_distances'),('plot_kde_projections','projections')]:
                stack.enter_context(patch.object(native,name,tagged(tag,getattr(native,name))))
            stack.enter_context(patch.object(native.ChromatinTraceTable,'barcode_statistics',capture_barcodes))
            stack.enter_context(patch.object(native.ChromatinTraceTable,'plots_barcode_statistics',
                tagged('barcode_frequencies',native.ChromatinTraceTable.plots_barcode_statistics)))
            native.process_traces({'trace_files':['trace.ecsv'],'plotXYZ':False,'format':output_format,'neighbor_distance_range':distance_range})
        success=True
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}'
        traceback.print_exc()
    finally:
        # Native labels are retained after the native function assigned them, not inferred from pixels.
        for call in calls:
            ax=call.pop('_axes',None)
            if ax is not None:call['barcode_labels']=[label.get_text() for label in ax.get_xticklabels()]
        plt.close('all')
        np.savez_compressed('numerical_outputs.npz',**arrays)
        doc={'status':'COMPLETE' if success else 'PARTIAL_ERROR','seed':seed,'numpy_version':np.__version__,
             'matplotlib_version':matplotlib.__version__,'capture_policy':'native-return-values-and-native-plotting-inputs-v1',
             'plot_calls':calls,'returned_values':returns,
             'warnings':[f'{w.category.__name__}: {w.message}' for w in caught], 'error':error}
        Path('numerical_outputs.json').write_text(json.dumps(doc,indent=2,allow_nan=False))
    return 0 if success else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--format',choices=['png','svg','pdf'],required=True)
    parser.add_argument('--distance-range',required=True)
    parser.add_argument('--seed',type=int,required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.format,args.distance_range,args.seed))
