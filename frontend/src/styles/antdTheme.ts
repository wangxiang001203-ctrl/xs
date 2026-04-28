import { theme } from 'antd'

export const antdTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#2f7d86',
    colorBgBase: '#edf7f6',
    colorBgContainer: 'rgba(255, 255, 255, 0.9)',
    colorBgElevated: '#fffefa',
    colorBorder: 'rgba(77, 128, 134, 0.2)',
    colorBorderSecondary: 'rgba(77, 128, 134, 0.14)',
    colorText: '#213c42',
    colorTextSecondary: '#536f73',
    colorTextTertiary: '#8da1a1',
    colorSuccess: '#398b68',
    colorWarning: '#be7b26',
    colorError: '#bd4d45',
    colorInfo: '#367f9a',
    borderRadius: 14,
    fontFamily: "'LXGW WenKai Screen', 'STKaiti', 'KaiTi', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
    fontSize: 13,
    controlHeight: 34,
    lineHeight: 1.6,
  },
  components: {
    Layout: {
      siderBg: 'rgba(255, 255, 255, 0.78)',
      headerBg: 'rgba(255, 255, 255, 0.78)',
      bodyBg: '#edf7f6',
    },
    Menu: {
      itemSelectedBg: 'rgba(47, 125, 134, 0.14)',
      itemHoverBg: 'rgba(47, 125, 134, 0.08)',
      itemHeight: 34,
    },
    Tabs: {
      cardBg: 'rgba(255, 255, 255, 0.68)',
    },
    Card: {
      colorBgContainer: 'rgba(255, 255, 255, 0.9)',
      boxShadowTertiary: '0 12px 34px rgba(42, 92, 99, 0.12)',
    },
  },
}
