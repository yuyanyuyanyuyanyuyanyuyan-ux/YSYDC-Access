Page({
  goRegister() {
    wx.navigateTo({
      url: '/pages/register/register'
    })
  },
  // 跳转管理员登录页面
  goAdminLogin() {

  wx.navigateTo({
    url: '/pages/admin-login/admin-login'
  })

}
})