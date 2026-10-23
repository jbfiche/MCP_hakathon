"""Isolated native localization figure and capture of existing plot data/results."""
import argparse
import json
import warnings
from pathlib import Path
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np
from traceratops import localization_analyzer as native


def run(output_format):
    arrays={};calls=[]
    def save(value,label):
        data=np.ma.asarray(value)
        if data.dtype.kind=='O':raise ValueError('Object arrays are not valid numerical evidence')
        key=f'{len(arrays):04d}_{label}';arrays[key]=np.asarray(data.data).copy()
        if np.ma.getmaskarray(data).any():arrays[key+'_mask']=np.ma.getmaskarray(data).copy()
        return key
    def intercept(method,original):
        def call(self,*args,**kwargs):
            entry={'method':method}
            if method=='violinplot':
                entry['datasets']=[save(v,'snr_by_barcode') for v in args[0]]
                entry['positions']=save(kwargs['positions'],'barcode_positions')
            elif method=='scatter':
                entry.update(x=save(args[0],'scatter_x'),y=save(args[1],'scatter_y'),color=save(kwargs['c'],'scatter_colors'))
            elif method=='bar':
                entry.update(positions=save(args[0],'barcode_ids'),counts=save(args[1],'detection_counts'))
            result=original(self,*args,**kwargs)
            if method=='violinplot':
                entry['native_density_vertices']=[save(body.get_paths()[0].vertices,'violin_vertices') for body in result['bodies']]
                entry['native_summary_segments']={key:save(result[key].get_segments(),key) for key in ['cmedians','cbars','cmins','cmaxes']}
            if method=='scatter':entry['rendered_offsets']=save(result.get_offsets(),'scatter_offsets')
            calls.append(entry)
            return result
        return call
    try:
        with warnings.catch_warnings(record=True) as caught,context_stack() as stack:
            warnings.simplefilter('always')
            for method in ['violinplot','scatter','bar']:
                stack.enter_context(patch.object(Axes,method,intercept(method,getattr(Axes,method))))
            native.run({'localization_file':'localizations.ecsv','output_file':'localization_distribution_fluxes.'+output_format,'format':output_format})
        if [c['method'] for c in calls]!=['violinplot','scatter','bar','scatter']:
            raise ValueError('Native plotting interface changed or legacy plotting was skipped')
        bars=next(c for c in calls if c['method']=='bar')
        counts=[{'barcode':int(b),'count':int(n)} for b,n in zip(arrays[bars['positions']],arrays[bars['counts']])]
        detail={'schema_version':1,'status':'COMPLETE','native_return_value':None,'native_barcode_counts':counts,
                'plot_calls':calls,'warnings':[f'{w.category.__name__}: {w.message}' for w in caught],
                'numpy_version':np.__version__,'matplotlib_version':matplotlib.__version__,
                'capture':'Native plot inputs and returned Matplotlib violin/offset values; no added scientific calculations.'}
        np.savez_compressed('numerical_outputs.npz',**arrays)
        Path('numerical_outputs.json').write_text(json.dumps(detail,indent=2,allow_nan=False))
    finally:plt.close('all')


def context_stack():
    from contextlib import ExitStack
    return ExitStack()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--format',choices=['png','svg','pdf'],default='png')
    run(parser.parse_args().format)
