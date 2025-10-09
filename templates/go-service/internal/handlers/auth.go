package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"

	"{{ module_name }}/internal/config"
	"{{ module_name }}/internal/logger"
	{{- if include_database }}
	"{{ module_name }}/internal/database"
	{{- endif }}
)

type LoginRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=6"`
}

type RegisterRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=6"`
	Name     string `json:"name" binding:"required"`
}

type AuthResponse struct {
	Token     string `json:"token"`
	ExpiresAt int64  `json:"expires_at"`
	User      User   `json:"user"`
}

type User struct {
	ID    string `json:"id"`
	Email string `json:"email"`
	Name  string `json:"name"`
}

// Login handler
func Login(cfg *config.Config, log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req LoginRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid request body",
				"details": err.Error(),
			})
			return
		}

		// TODO: Implement actual authentication logic
		// For now, this is a mock implementation
		if req.Email != "admin@example.com" || req.Password != "password" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Invalid credentials",
			})
			return
		}

		// Generate JWT token
		token, expiresAt, err := generateToken(cfg.JWTSecret, "1", req.Email)
		if err != nil {
			log.Errorf("Failed to generate token: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to generate token",
			})
			return
		}

		user := User{
			ID:    "1",
			Email: req.Email,
			Name:  "Admin User",
		}

		c.JSON(http.StatusOK, AuthResponse{
			Token:     token,
			ExpiresAt: expiresAt,
			User:      user,
		})
	}
}

// Register handler
func Register(cfg *config.Config, log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req RegisterRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid request body",
				"details": err.Error(),
			})
			return
		}

		// TODO: Implement actual user registration logic
		// For now, this is a mock implementation

		// Generate JWT token
		token, expiresAt, err := generateToken(cfg.JWTSecret, "2", req.Email)
		if err != nil {
			log.Errorf("Failed to generate token: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to generate token",
			})
			return
		}

		user := User{
			ID:    "2",
			Email: req.Email,
			Name:  req.Name,
		}

		c.JSON(http.StatusCreated, AuthResponse{
			Token:     token,
			ExpiresAt: expiresAt,
			User:      user,
		})
	}
}

// RefreshToken handler
func RefreshToken(cfg *config.Config, log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		// TODO: Implement token refresh logic
		c.JSON(http.StatusNotImplemented, gin.H{
			"error": "Token refresh not implemented",
		})
	}
}

// GetProfile handler
func GetProfile(log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetString("user_id")
		email := c.GetString("email")

		// TODO: Fetch user from database
		user := User{
			ID:    userID,
			Email: email,
			Name:  "User Name",
		}

		c.JSON(http.StatusOK, user)
	}
}

func generateToken(secret, userID, email string) (string, int64, error) {
	expiresAt := time.Now().Add(24 * time.Hour).Unix()

	claims := jwt.MapClaims{
		"user_id": userID,
		"email":   email,
		"exp":     expiresAt,
		"iat":     time.Now().Unix(),
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(secret))
	if err != nil {
		return "", 0, err
	}

	return tokenString, expiresAt, nil
}
