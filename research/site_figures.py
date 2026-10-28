"""Publication figures for the US-market and saved-option studies."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
IMAGES=ROOT/'assets/images'
BLUE='#234d70';RUST='#985141';GREY='#8b949d';INK='#19232d'


def save(fig,name):
    path=IMAGES/f'{name}.svg'
    fig.savefig(path,bbox_inches='tight',metadata={'Date':None,'Creator':'Afsar Sharif'})
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)


def time_axis(ax):
    loc=mdates.AutoDateLocator(minticks=4,maxticks=7)
    ax.xaxis.set_major_locator(loc);ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    ax.grid(axis='y',alpha=.18)


def build_figures():
    from research.strategist_lab.reports import style
    style()
    daily=pd.read_csv(ROOT/'research/site_data/us_market_daily.csv',index_col=0,parse_dates=True)
    tapes=pd.read_csv(ROOT/'research/site_data/us_market_tape_share.csv',index_col=0)
    changes=pd.read_csv(ROOT/'research/site_data/us_market_share_changes.csv',index_col=0)
    fig,ax=plt.subplots(2,1,figsize=(11,6.5),sharex=True,layout='constrained')
    ax[0].plot(daily.index,daily['Total Notional']/1e9,color=BLUE,lw=1.3)
    ax[0].set_ylabel('Trading value ($bn)')
    ax[0].set_title('US trading value and off-exchange share, 2025',loc='left',pad=17)
    ax[1].plot(daily.index,daily['Off-exchange share'],color=GREY,lw=.9,label='Daily share')
    ax[1].plot(daily.index,daily['Off-exchange share (20D)'],color=BLUE,lw=1.8,label='20-day average')
    ax[1].axhline(daily['Off-exchange share'].mean(),color=RUST,lw=1,ls='--',label='Year average')
    ax[1].yaxis.set_major_formatter(PercentFormatter(1));ax[1].set_ylabel('Off-exchange share')
    ax[1].legend(frameon=False,ncol=3,fontsize=9,loc='lower left')
    for a in ax:time_axis(a)
    save(fig,'us_market_overview')
    names=[x.replace(' Equities','').replace(' (Q)','').replace(' (N)','').replace(' (P)','') for x in tapes.index]
    cmap=LinearSegmentedColormap.from_list('research_blue',['#fff','#a9bfd0',BLUE])
    fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
    image=ax.imshow(tapes.to_numpy()*100,cmap=cmap,aspect='auto',vmin=0,vmax=60)
    ax.set_yticks(range(len(names)),names);ax.set_xticks(range(3),['Tape A · NYSE','Tape B · Other','Tape C · Nasdaq'])
    ax.set_title('Exchange share within each listing group',loc='left',pad=18)
    for i in range(len(names)):
        for j in range(3):
            v=tapes.iloc[i,j]*100;ax.text(j,i,f'{v:.1f}%',ha='center',va='center',color='white' if v>35 else INK,fontsize=10)
    ax.tick_params(length=0);fig.colorbar(image,ax=ax,shrink=.8,label='Share of annual on-exchange value (%)')
    save(fig,'us_tape_structure')
    high=daily['Total Notional']>=daily['Total Notional'].quantile(.90)
    rng=np.random.default_rng(91)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,column,title,color in [(axes[0],'Off-exchange share','Off-exchange share',BLUE),(axes[1],'Exchange HHI','Exchange concentration (HHI)',RUST)]:
        groups=[daily.loc[~high,column].to_numpy(),daily.loc[high,column].to_numpy()]
        boxes=ax.boxplot(groups,positions=[0,1],widths=.45,patch_artist=True,showfliers=False,
            medianprops={'color':INK,'linewidth':1.2},boxprops={'edgecolor':color},whiskerprops={'color':color},capprops={'color':color})
        for patch in boxes['boxes']:patch.set_facecolor(color+'18')
        for i,values in enumerate(groups):ax.scatter(i+rng.uniform(-.16,.16,len(values)),values,s=10,color=color,alpha=.35,zorder=3)
        ax.set_xticks([0,1],['Other 225 days','Busiest 25 days']);ax.set_title(title,loc='left',pad=18);ax.grid(axis='y',alpha=.18)
    axes[0].yaxis.set_major_formatter(PercentFormatter(1));save(fig,'us_activity_regimes')
    chosen=pd.concat([changes.head(5),changes.tail(5)]).sort_values('Change (pp)')
    fig,ax=plt.subplots(figsize=(10,5.5),layout='constrained')
    ax.barh(chosen.index,chosen['Change (pp)'],color=[BLUE if x>=0 else RUST for x in chosen['Change (pp)']],height=.58)
    ax.axvline(0,color=GREY,lw=.8);ax.set_xlabel('Change in share (percentage points)')
    ax.set_title('Exchange-share change: fourth quarter versus first quarter',loc='left',pad=18);ax.grid(axis='x',alpha=.15)
    save(fig,'us_share_shifts')
    spy_figures()


def spy_figures():
    d=pd.read_csv(ROOT/'code/volatility_surface/spy_iv_snapshot_sample.csv')
    latest=d.loc[d.snapshot_time==d.snapshot_time.max()].copy();spot=float(latest.spot.iloc[0])
    latest.expiration=pd.to_datetime(latest.expiration.astype(str),format='%Y%m%d')
    observed=latest.pivot_table(index='expiration',columns='strike',values='iv').sort_index().sort_index(axis=1)
    surface=observed.interpolate(axis=1,limit_direction='both').interpolate(axis=0,limit_direction='both')
    x,y=np.meshgrid(surface.columns.to_numpy(),np.arange(len(surface)))
    fig=plt.figure(figsize=(12,5.7));grid=fig.add_gridspec(1,2,width_ratios=[1.35,1])
    fig.subplots_adjust(left=.015,right=.98,bottom=.14,top=.88,wspace=.30)
    ax=fig.add_subplot(grid[0,0],projection='3d');right=fig.add_subplot(grid[0,1])
    ax.plot_surface(x,y,surface.to_numpy()*100,cmap='cividis',alpha=.9,edgecolor='#ffffff99',linewidth=.35)
    for i in range(len(observed)):
        mask=observed.iloc[i].notna().to_numpy();ax.scatter(observed.columns[mask],np.full(mask.sum(),i),observed.iloc[i,mask]*100,color=INK,s=8,depthshade=False)
    ax.set_xlabel('Strike ($)',labelpad=8);ax.set_ylabel('Expiry',labelpad=8);ax.set_zlabel('Implied volatility (%)',labelpad=5)
    ax.set_yticks(range(len(observed)),[x.strftime('%d %b') for x in observed.index]);ax.view_init(elev=24,azim=-61)
    ax.tick_params(labelsize=8);ax.set_title('SPY option volatility',loc='left',pad=14)
    front=observed.iloc[0].dropna()*100
    right.plot(front.index,front.values,color=BLUE,lw=1.6,marker='o',ms=4)
    right.axvline(spot,color=RUST,ls='--',lw=1,label=f'SPY price ${spot:,.2f}')
    right.set_title('Nearest expiry · 8 September 2026',loc='left',pad=18)
    right.set_xlabel('Strike ($)');right.set_ylabel('Implied volatility (%)');right.grid(axis='y',alpha=.18);right.legend(frameon=False,fontsize=9)
    save(fig,'spy_option_volatility')
    fig,ax=plt.subplots(figsize=(10,3.4),layout='constrained')
    for i in range(len(observed)):
        mask=observed.iloc[i].notna().to_numpy()
        ax.scatter(np.flatnonzero(mask),np.full(mask.sum(),i),s=48,color=BLUE,label='Observed' if i==0 else None)
        ax.scatter(np.flatnonzero(~mask),np.full((~mask).sum(),i),s=48,facecolors='none',edgecolors=GREY,label='Missing' if i==0 else None)
    ax.set_xticks(range(len(observed.columns)),[f'${x:,.0f}' for x in observed.columns]);ax.set_yticks(range(len(observed.index)),[x.strftime('%d %b %Y') for x in observed.index]);ax.invert_yaxis()
    ax.set_ylim(len(observed)-.5,-.7);ax.set_xlim(-.5,len(observed.columns)-.5);ax.set_title('Observed points in the latest capture',loc='left',pad=18)
    ax.legend(frameon=False,ncol=2,loc='upper right',bbox_to_anchor=(1,1.25),fontsize=9)
    ax.set_xlabel('Strike');ax.grid(axis='y',alpha=.15);save(fig,'spy_option_coverage')


if __name__=='__main__':build_figures()
