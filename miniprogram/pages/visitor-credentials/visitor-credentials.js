Page({
  data: {
    list: []
  },

  onShow() {
    const userId = wx.getStorageSync('user_id')
    if (!userId) {
      wx.reLaunch({ url: '/pages/visitor-login/visitor-login' })
      return
    }
    wx.request({
      url: `http://127.0.0.1:8000/api/visitor/credentials/${userId}`,
      method: 'GET',
      success: (res) => {
        if (res.data.success) {
          this.setData({ list: res.data.list || [] })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' })
    })
  }
})
