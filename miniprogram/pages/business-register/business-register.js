const { BASE_URL } = require('../../config')

Page({
  data: {
    username: '',
    password: '',
    real_name: '',
    phone: ''
  },

  input(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  register() {
    const { username, password, real_name, phone } = this.data
    if (!username.trim() || !password) {
      wx.showToast({ title: '请输入账号和密码', icon: 'none' })
      return
    }
    wx.showLoading({ title: '注册中' })
    wx.request({
      url: BASE_URL + '/api/business/register',
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: { username, password, real_name, phone },
      success: (res) => {
        if (res.data.success) {
          wx.showToast({ title: '注册成功，请登录', icon: 'success' })
          setTimeout(() => wx.navigateBack(), 1200)
        } else {
          wx.showToast({ title: res.data.message || '注册失败', icon: 'none' })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' }),
      complete: () => wx.hideLoading()
    })
  }
})
