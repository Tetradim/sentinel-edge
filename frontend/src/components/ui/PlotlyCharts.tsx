/**
 * Advanced Plotly Chart Components
 * Supports: Area, Bar, Line, Candlestick charts
 * With resizable layouts: Grid, List, Heatmap
 */
import React, { useState, useMemo, useRef, useEffect } from 'react';
import PlotModule from 'react-plotly.js';
import { 
  BarChart3, 
  TrendingUp, 
  Activity, 
  Grid3X3, 
  List, 
  LayoutGrid,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { cn } from '@/lib/utils';

const Plot = (PlotModule as any).default ?? PlotModule;

// Chart type definitions
export type ChartType = 'area' | 'bar' | 'line' | 'candlestick' | 'heatmap';

// Layout types for dashboards
export type LayoutType = 'grid' | 'list' | 'heatmap';

interface PlotlyChartProps {
  data: any[];
  layout?: any;
  config?: any;
  className?: string;
  height?: number;
  useResizeHandler?: boolean;
}

// Base Plotly Chart Component
export const PlotlyChart: React.FC<PlotlyChartProps> = ({
  data,
  layout = {},
  config = {},
  className,
  height = 400,
  useResizeHandler = true
}) => {
  return (
    <div className={cn("w-full", className)}>
      <Plot
        data={data}
        layout={{
          ...layout,
          height,
          autosize: true,
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          font: {
            color: '#9ca3af'
          },
          xaxis: {
            gridcolor: '#374151',
            linecolor: '#4b5563',
            tickfont: { color: '#9ca3af' },
            ...layout.xaxis
          },
          yaxis: {
            gridcolor: '#374151',
            linecolor: '#4b5563',
            tickfont: { color: '#9ca3af' },
            ...layout.yaxis
          },
          margin: { l: 60, r: 20, t: 40, b: 40, ...layout.margin }
        }}
        config={{
          displayModeBar: false,
          responsive: true,
          ...config
        }}
        style={{ width: '100%', height }}
        useResizeHandler={useResizeHandler}
      />
    </div>
  );
};

// Chart type selector component
interface ChartTypeSelectorProps {
  value: ChartType;
  onChange: (type: ChartType) => void;
  className?: string;
}

export const ChartTypeSelector: React.FC<ChartTypeSelectorProps> = ({
  value,
  onChange,
  className
}) => {
  const chartTypes: { type: ChartType; icon: React.ReactNode; label: string }[] = [
    { type: 'area', icon: <Activity className="w-4 h-4" />, label: 'Area' },
    { type: 'bar', icon: <BarChart3 className="w-4 h-4" />, label: 'Bar' },
    { type: 'line', icon: <TrendingUp className="w-4 h-4" />, label: 'Line' },
    { type: 'candlestick', icon: <Activity className="w-4 h-4" />, label: 'Candle' },
    { type: 'heatmap', icon: <Grid3X3 className="w-4 h-4" />, label: 'Heat' },
  ];

  return (
    <div className={cn("flex gap-1 p-1 bg-gray-800 rounded-lg", className)}>
      {chartTypes.map(({ type, icon, label }) => (
        <button
          key={type}
          onClick={() => onChange(type)}
          className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
            value === type 
              ? "bg-emerald-500 text-white" 
              : "text-gray-400 hover:text-white hover:bg-gray-700"
          )}
        >
          {icon}
          {label}
        </button>
      ))}
    </div>
  );
};

// Generate chart data based on type
export function generateChartData(
  type: ChartType,
  xData: any[],
  yData: number[],
  name: string = "Value",
  options?: {
    open?: number[];
    high?: number[];
    low?: number[];
    close?: number[];
    values?: number[][]; // For heatmap
  }
) {
  switch (type) {
    case 'area':
      return [{
        x: xData,
        y: yData,
        type: 'scatter',
        fill: 'tozeroy',
        fillcolor: 'rgba(16, 185, 129, 0.2)',
        line: { color: '#10b981', width: 2 },
        name
      }];
    
    case 'bar':
      return [{
        x: xData,
        y: yData,
        type: 'bar',
        marker: {
          color: yData.map(v => v >= 0 ? '#10b981' : '#ef4444'),
          opacity: 0.8
        },
        name
      }];
    
    case 'line':
      return [{
        x: xData,
        y: yData,
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#10b981', width: 2 },
        marker: { size: 4 },
        name
      }];
    
    case 'candlestick':
      if (!options?.open || !options?.high || !options?.low || !options?.close) {
        // Fallback to line if no OHLC data
        return generateChartData('line', xData, yData, name);
      }
      return [{
        x: xData,
        close: options.close,
        decreasing: { line: { color: '#ef4444' } },
        high: options.high,
        increasing: { line: { color: '#10b981' } },
        low: options.low,
        open: options.open,
        type: 'candlestick',
        xaxis: 'x',
        yaxis: 'y'
      }];
    
    case 'heatmap':
      return [{
        x: xData,
        y: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        z: options?.values || [[1,2,3,4,5]],
        type: 'heatmap',
        colorscale: [
          [0, '#0a2e1f'],
          [0.5, '#10b981'],
          [1, '#059669']
        ],
        showscale: true
      }];
    
    default:
      return generateChartData('line', xData, yData, name);
  }
}

// Resizable Card with multiple layout options
interface ResizableCardProps {
  children: React.ReactNode;
  layout: LayoutType;
  className?: string;
  title?: string;
  onLayoutChange?: (layout: LayoutType) => void;
}

export const ResizableCard: React.FC<ResizableCardProps> = ({
  children,
  layout,
  className,
  title,
  onLayoutChange
}) => {
  const layouts: { type: LayoutType; icon: React.ReactNode }[] = [
    { type: 'grid', icon: <LayoutGrid className="w-4 h-4" /> },
    { type: 'list', icon: <List className="w-4 h-4" /> },
    { type: 'heatmap', icon: <Grid3X3 className="w-4 h-4" /> },
  ];

  const gridClasses = {
    grid: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
    list: "flex flex-col gap-4", 
    heatmap: "grid grid-cols-7 gap-2"
  };

  return (
    <div className={cn(
      "bg-gray-800/50 rounded-xl border border-gray-700 overflow-hidden",
      className
    )}>
      {(title || onLayoutChange) && (
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          {title && <h3 className="text-lg font-semibold text-white">{title}</h3>}
          {onLayoutChange && (
            <div className="flex gap-1">
              {layouts.map(({ type, icon }) => (
                <button
                  key={type}
                  onClick={() => onLayoutChange(type)}
                  className={cn(
                    "p-2 rounded-lg transition-colors",
                    layout === type 
                      ? "bg-emerald-500 text-white" 
                      : "text-gray-400 hover:text-white hover:bg-gray-700"
                  )}
                >
                  {icon}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <div className={cn(gridClasses[layout], "p-4")}>
        {children}
      </div>
    </div>
  );
};

// Grid Layout Component
interface GridLayoutProps {
  children: React.ReactNode[];
  columns?: number;
  gap?: number;
}

export const GridLayout: React.FC<GridLayoutProps> = ({
  children,
  columns = 2,
  gap = 4
}) => {
  return (
    <div 
      className="grid gap-4"
      style={{ 
        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` 
      }}
    >
      {children}
    </div>
  );
};

// List Layout Component  
interface ListLayoutProps {
  children: React.ReactNode[];
  direction?: 'row' | 'column';
}

export const ListLayout: React.FC<ListLayoutProps> = ({
  children,
  direction = 'row'
}) => {
  return (
    <div className={cn(
      "flex gap-4",
      direction === 'row' ? "flex-row overflow-x-auto" : "flex-col"
    )}>
      {children}
    </div>
  );
};

// Heatmap Layout Component
interface HeatmapLayoutProps {
  data: number[][];
  labels?: {
    x: string[];
    y: string[];
  };
  colorScale?: [number, string][];
}

export const HeatmapLayout: React.FC<HeatmapLayoutProps> = ({
  data,
  labels = { x: [], y: [] },
  colorScale = [
    [0, '#0a2e1f'],
    [0.5, '#10b981'],
    [1, '#059669']
  ]
}) => {
  const chartData = useMemo(() => [{
    x: labels.x,
    y: labels.y,
    z: data,
    type: 'heatmap',
    colorscale: colorScale,
    showscale: true,
    hovertemplate: 'Value: %{z}<extra></extra>'
  }], [data, labels, colorScale]);

  return <PlotlyChart data={chartData} height={300} />;
};

// Compact Chart Card for dashboards
interface ChartCardCompactProps {
  title: string;
  chartType: ChartType;
  onChartTypeChange: (type: ChartType) => void;
  data: any[];
  layout?: LayoutType;
  onLayoutChange?: (layout: LayoutType) => void;
}

export const ChartCardCompact: React.FC<ChartCardCompactProps> = ({
  title,
  chartType,
  onChartTypeChange,
  data,
  layout = 'grid',
  onLayoutChange
}) => {
  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700">
      <div className="flex items-center justify-between p-3 border-b border-gray-700">
        <span className="text-sm font-medium text-white">{title}</span>
        <div className="flex items-center gap-2">
          <ChartTypeSelector 
            value={chartType} 
            onChange={onChartTypeChange}
            className="scale-90"
          />
          {onLayoutChange && (
            <button
              onClick={() => onLayoutChange(
                layout === 'grid' ? 'list' : layout === 'list' ? 'heatmap' : 'grid'
              )}
              className="p-1.5 text-gray-400 hover:text-white"
            >
              {layout === 'grid' && <LayoutGrid className="w-4 h-4" />}
              {layout === 'list' && <List className="w-4 h-4" />}
              {layout === 'heatmap' && <Grid3X3 className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>
      <div className="p-3">
        <PlotlyChart data={data} height={280} />
      </div>
    </div>
  );
};

export default {
  PlotlyChart,
  ChartTypeSelector,
  generateChartData,
  ResizableCard,
  GridLayout,
  ListLayout,
  HeatmapLayout,
  ChartCardCompact
};
