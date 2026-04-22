import { theme } from 'antd'

export const antdTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#c0392b',
    colorBgBase: '#0d0d0d',
    colorBgContainer: '#1c1c1c',
    colorBgElevated: '#242424',
    colorBorder: '#2c2c2c',
    colorBorderSecondary: '#383838',
    colorText: '#e0d8cc',
    colorTextSecondary: '#8a8070',
    colorTextTertiary: '#4a4540',
    colorSuccess: '#27ae60',
    colorWarning: '#e67e22',
    colorError: '#c0392b',
    colorInfo: '#2980b9',
    borderRadius: 5,
    fontFamily: "'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
    fontSize: 13,
    controlHeight: 30,
    lineHeight: 1.6,
  },
  components: {
    Layout: {
      siderBg: '#141414',
      headerBg: '#141414',
      bodyBg: '#0d0d0d',
    },
    Menu: {
      darkItemBg: '#141414',
      darkSubMenuItemBg: '#1c1c1c',
      darkItemSelectedBg: '#2a2a2a',
      darkItemHoverBg: '#242424',
      itemHeight: 32,
    },
    Tabs: {
      cardBg: '#1c1c1c',
    },
  },
}
